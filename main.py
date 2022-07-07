import os
import os.path

from rich.console import Console

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

import config

from logger import logger


def create_image_folder(folder, folder_id, service, console) -> str:
    img_metadata = {
        'name': config.IMG_FOLDER,
        'mimeType': config.MIME_TYPE,
        'parents': [folder_id]
    }
    img_folder = service.files() \
                        .create(body=img_metadata, fields='id') \
                        .execute()
    img_folder_id = img_folder.get('id')

    console.print(
        f' [•] Created an image folder for {folder}.',
        style='bold green'
    )

    return img_folder_id


def create_files(
        parent,
        folder,
        folder_id,
        service,
        console,
        is_img_folder=False) -> None:
    response = service.files().list(
        q=f"parents='{folder_id}'",
        fields='files(id, name)'
    ).execute()['files']

    folder_path = os.path.abspath(f'{parent}/{folder}')
    folder_files = os.listdir(folder_path)
    not_created_files: list[str] = [
        item['name'] for item in response if item['name'] not in folder_files
    ]

    if not is_img_folder and config.IMG_FOLDER in not_created_files:
        img_folder_id = create_image_folder(
            folder=folder,
            folder_id=folder_id,
            service=service,
            console=console
        )
        create_files(
            parent=f'{parent}/{folder}',
            folder=config.IMG_FOLDER,
            folder_id=img_folder_id,
            service=service,
            console=console,
            is_img_folder=True
        )

    for file in os.listdir(folder_path):
        file_path = f'{folder_path}/{file}'

        if os.path.isdir(os.path.abspath(file_path)) or file not in not_created_files:
            continue

        file_metadata = {
            'name': file,
            'parents': [folder_id]
        }

        media = MediaFileUpload(file_path)

        service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        console.print(f' [•] Backed up a file: {file}', style='bold green')


def create_folders(parent, folder_id, service, console: Console) -> None:
    parent_folder = service.files().list(
        q=f'parents="{folder_id}"',
        spaces='drive',
        fields='files(id, name)'
    ).execute()

    folders = [folder for folder in parent_folder['files']]

    for folder in os.listdir(os.path.abspath(parent)):
        if os.path.isfile(folder):
            console.print(f' [•] Can not create {folder}. It is a file.', style='red bold')
            continue

        if folder == config.OBSIDIAN_FOLDER or folder.startswith('.'):
            console.print(f' [•] Can not create {folder}. It is a secret folder.', style='red bold')
            continue

        if folder in [item['name'] for item in folders]:
            console.print(f' [•] Folder {folder} already exists in the drive.', style='red bold')
            continue

        file_metadata = {
            'name': folder,
            'mimeType': config.MIME_TYPE,
            'parents': [folder_id]
        }

        for item in folders:
            if item['name'] == folder:
                drive_folder = service.files().list(
                    q=f'name="{folder}"',
                    spaces='drive',
                    fields='files(id, name)'
                ).execute()
                drive_folder_id = drive_folder['files'][0]['id']
                break

        if not drive_folder:
            drive_folder = service.files().create(body=file_metadata).execute()
            drive_folder_id = drive_folder.get('id')
            console.print(
                f' [•] Created a folder: {drive_folder["name"]}',
                style='bold green'
            )

        create_files(
            parent=parent,
            folder=folder,
            folder_id=drive_folder_id,
            service=service,
            console=console
        )


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


def main() -> None:
    console = Console()

    console.print(' [•] Checking for a token file...', style='green bold')
    creds, message = try_get_from_token_file()
    console.print(message, style='green bold')

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                config.CREDENTIALS_FILE, config.SCOPES)
            creds = flow.run_local_server(port=0)
        console.print(' [•] Creating a token file...', style='green bold')
        with open(config.TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
        console.print(' [•] The token file created', style='green bold')

    try:
        service = build('drive', 'v3', credentials=creds)

        response = service.files().list(
            q=f'name="{config.BACKUP_FOLDER}" and mimeType="{config.MIME_TYPE}"',
            spaces='drive'
        ).execute()

        if not response['files']:
            file_metadata = {
                'name': config.BACKUP_FOLDER,
                'mimeType': config.MIME_TYPE
            }

            folder = service.files() \
                            .create(body=file_metadata, fields='id') \
                            .execute()

            folder_id = folder.get('id')
        else:
            folder_id = response['files'][0]['id']

        try:
            console.print(' [•] Start creating folders...', style='green bold')
            create_folders(config.BACKUP_FOLDER, folder_id, service, console)
            console.print(' [•] All done.', style='blue bold')
        except FileNotFoundError as e:
            logger.error(e)
    except HttpError as e:
        logger.error(e.content.decode())


if __name__ == '__main__':
    main()
