import os
import os.path

from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

import config

from utils import console, logger


def create_file(service, body: dict, media_body: MediaFileUpload):
    service.files().create(
        body=body,
        media_body=media_body,
    ).execute()


def create_folder(service, body):
    folder = service.files().create(
        body=body,
        fields='id'
    ).execute()
    return folder


def create_files(service, folder: str, folder_id):
    folder_path = os.path.abspath(folder)

    for file in os.listdir(folder_path):
        file_path = os.path.abspath(f'{folder}/{file}')
        
        if os.path.isdir(file_path):
            if file.startswith('.'):
                console.print(f' [•] Can not backup {file}. It\'s a secret folder.', style='red bold')
            folder_metadata = {
                'name': file,
                'mimeType': config.MIME_TYPE,
                'parents': [folder_id]
            }

            child_folder : dict = create_folder(service, folder_metadata)
            console.print(f' [•] Create the folder {file} for {folder}', style='green bold')

            create_files(
                service=service,
                folder=f"{folder}/{file}",
                folder_id=child_folder.get('id')
            )
            continue

        file_metadata = {
            'name': file,
            'parents': [folder_id]
        }

        media_file_upload = MediaFileUpload(file_path)

        try:
            create_file(service, file_metadata, media_file_upload)
        except HttpError:
            console.print(f' [•] Can not backup {file}', style='red bold')
            continue

        console.print(f' [•] Backed up a file: {file}', style='green bold')


def try_get_from_token_file() -> tuple[Credentials | None, str]:
    message = ' [•] The token files does not exists.'
    credentials = None

    if os.path.exists(config.TOKEN_FILE):
        credentials = Credentials.from_authorized_user_file(
            config.TOKEN_FILE,
            config.SCOPES
        )
        message = ' [•] Getting credentials from a token file'

    return credentials, message


def get_credentials() -> Credentials:
    console.print(' [•] Checking for a token file...', style='green bold')
    credentials, message = try_get_from_token_file()
    console.print(message, style='green bold')

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                config.CREDENTIALS_FILE, config.SCOPES)
            credentials = flow.run_local_server(port=0)
        console.print(' [•] Creating a token file...', style='green bold')
        with open(config.TOKEN_FILE, 'w') as token:
            token.write(credentials.to_json())
        console.print(' [•] The token file created', style='green bold')
    return credentials


def build_service(credentials):
    return build('drive', 'v3', credentials=credentials)


def backup_files() -> None:
    try:
        credentials = get_credentials()
    except Exception:
        console.print(' [•] Something went wrong...', style='red bold')
        return
    
    try:
        service = build_service(credentials=credentials)
        folder_metadata = {
            'name': f'{config.BACKUP_FOLDER}-{datetime.now().strftime("%m.%d.%y-%H:%M:%S")}',
            'mimeType': config.MIME_TYPE
        }
        folder = service.files().create(
            body=folder_metadata,
            fields='id'
        ).execute()
        folder_id = folder.get('id')
        
        console.print(' [•] Start creating folders...', style='green bold')
        create_files(
            service=service,
            folder=config.BACKUP_FOLDER,
            folder_id=folder_id
        )
        console.print(' [•] All done.', style='blue bold')
    except HttpError as e:
        logger.error(e)


def choose_command():
    console.print(' [•] B - Backup\n [•] D - Download\n [•] E - Exit', style='blue bold')
    while True:
        command = console.input(' [•] Enter the command: ')
        if command in ['B', 'D', 'E']:
            return command
        console.print(' [•] Unknown command... Try again.', style='yellow bold')
        

def main():
    try:
        command = choose_command()
        match command:
            case 'B':
                backup_files()
            case 'D':
                console.print(' [•] Comming soon...', style='yellow bold')
                # download_files()
                return
            case 'E':
                console.print(' [•] Exit from program...', style='blue bold')
                return
    except KeyboardInterrupt | Exception:
        return


if __name__ == '__main__':
    main()
