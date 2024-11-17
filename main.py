import glob
import logging
import os
from time import sleep

import requests  # pip install requests

# Change the path to match your unzipped export from Runtastic
RUNTASTIC_EXPORT_FOLDER = os.getenv("RUNTASTIC_EXPORT_FOLDER", "./export-YOUR_FOLDER/")
RUNTASTIC_GPS_DATA_FOLDER = f"{RUNTASTIC_EXPORT_FOLDER}Sport-sessions/GPS-data/"
RUNTASTIC_FILE_SELECTOR = "*.gpx"  # You can filers like "2024-05*.gpx"

# Create your app - https://www.strava.com/settings/api - get CLIENT_ID and CLIENT_SECRET
STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID", "[INSERT YOUR CLIENT ID]")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET", "[INSERT YOUR CLIENT SECRET]")

# You can use a previous STRAVA_ACCESS_TOKEN if you already have one
STRAVA_ACCESS_TOKEN = os.getenv("STRAVA_ACCESS_TOKEN", "")
STRAVA_BASE_URL = "https://www.strava.com/api/v3"

# https://developers.strava.com/docs/rate-limits/
# Limits: 100 requests every 15 minutes and 1000 requests per day
# Error 429 if exceeding the limit
# Consider increasing this if uploading more than 100 activities
DELAY_SECONDS = 1  # Suggested: 9 seconds to avoid 15 minutes limit

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def load_raw_runtastic_gpx_activities_from_folder_iterator():
    log.info(f"Opening {RUNTASTIC_GPS_DATA_FOLDER}")
    matching_files = sorted(glob.glob(f"{RUNTASTIC_GPS_DATA_FOLDER}{RUNTASTIC_FILE_SELECTOR}"))
    count = len(matching_files)

    log.info(f"Found {count} matching activities")
    input(f"Press any key to contine and upload {count} activities")

    i = 0
    for path in matching_files:
        with open(path, "rb") as file:
            i += 1
            log.debug(f"[{i}/{count}] Loading {file.name.split('/')[-1]}")
            yield file

    log.info(f"{len(matching_files)} activities uploaded to Strava. Star this repository!")


def send_runtastic_files_to_strava(access_token: str):
    headers = {"Authorization": f"Bearer {access_token}"}
    session = requests.Session()

    for runtastic_activity_file in load_raw_runtastic_gpx_activities_from_folder_iterator():
        # https://developers.strava.com/docs/reference/#api-Uploads-createUpload

        response = session.post(
            url=f"{STRAVA_BASE_URL}/uploads",
            headers=headers,
            data={
                "name": "",
                "description": "Import from Runtastic.",
                "data_type": "gpx",
            },
            files={"file": runtastic_activity_file},
        )
        status_code = response.status_code
        if status_code == 201:
            log.info(f"OK - {response.text}")
        else:
            log.error(f"{status_code} - {response.text}")

        if status_code == 429:
            log.error("Stava exceeding rate-limit. Retry in the next 15 minutes")
        if status_code == 401:
            exit(1)

        sleep(DELAY_SECONDS)


def get_access_token_from_strava(code: str) -> str:
    # https://developers.strava.com/docs/authentication/
    # Token expires after 6 hours

    data = {
        "client_id": STRAVA_CLIENT_ID,
        "client_secret": STRAVA_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
    }
    response = requests.post(f"{STRAVA_BASE_URL}/oauth/token", data=data)
    log.info(f"Login {response.status_code} - response={response.text}")
    if response.status_code // 100 != 2:
        exit(1)
    return response.json()["access_token"]


if __name__ == "__main__":
    authorize_app_url = (
        f"https://www.strava.com/oauth/authorize?client_id={STRAVA_CLIENT_ID}"
        "&response_type=code&redirect_uri=http://localhost:8080"
        "&approval_prompt=force&scope=activity:write"
    )

    access_token = STRAVA_ACCESS_TOKEN
    if not access_token:
        print("+++ OPEN THE BROWSER IN THIS PAGE - LOGIN AND GET THE CODE FROM URL +++")
        print(authorize_app_url)

        code = input("Insert code>")
        access_token = get_access_token_from_strava(code)

    log.info(f"Sending data to Strava with access_token={access_token}")
    send_runtastic_files_to_strava(access_token)
