import asyncio
import json
import logging
import sys
import zipfile
from datetime import datetime
from os import getenv, mkdir, path, remove
from typing import List

import paramiko
import pytz
from aiogram import Bot, Dispatcher, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.utils.markdown import bold
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from scp import SCPClient

load_dotenv()


TOKEN = getenv("BOT_TOKEN")

CHAT_ID = int(getenv("CHAT_ID"))

PROXY_URL = getenv("PROXY_URL")

CRON_JOB = getenv("CRON_JOB")

TZ = getenv("TZ", "Asia/Tehran")

BACKUP_PATH = "./backups/"

BACKUP_FILE_NAME = "marzban-backup.zip"

# Path to store parts of large backups
PARTS_PATH = "./parts/"

# Maximum Telegram file size for bots (50 MB)
MAX_PART_SIZE = 50 * 1024 * 1024


with open("./server_list.json", "r") as jf:
    SERVER_LIST = json.loads(jf.read())


session = AiohttpSession()
if PROXY_URL:
    session.proxy = PROXY_URL

BOT = Bot(TOKEN, parse_mode=ParseMode.MARKDOWN, session=session)

dp = Dispatcher()

if not path.exists(BACKUP_PATH):
    mkdir(BACKUP_PATH)

if not path.exists(PARTS_PATH):
    mkdir(PARTS_PATH)


@dp.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    await message.answer(f"Hello, {bold(message.from_user.full_name)}!")


@dp.message(Command(commands="backup"))
async def send_full_backup_command(message: types.Message):
    if message.from_user.id == CHAT_ID:
        await send_full_backups()


def get_list_dir(ssh: paramiko.SSHClient, path) -> List[str]:
    stdin, stdout, stderr = ssh.exec_command(f"ls -a {path}")
    return stdout.read().decode().split()[2:]


def is_dir(ssh: paramiko.SSHClient, path) -> bool:
    stdin, stdout, stderr = ssh.exec_command(
        f'test -d {path}  && echo "is dir" || echo "isnt dir"')
    is_dir = stdout.read().decode().strip() == 'is dir'
    return is_dir


def get_date():
    return datetime.now(pytz.timezone(TZ)).strftime('%Y/%m/%d %H:%M:%S')


def _create_zipFile(ssh, scp_client_obj, zip_file_obj, remote_path, files, exclude):

    exclude_files_and_dirctories(exclude, files)

    for f in files:
        if is_dir(ssh, f"{remote_path}{f}"):
            _files = get_list_dir(ssh, f"{remote_path}{f}")
            zip_file_obj = _create_zipFile(
                ssh, scp_client_obj,
                zip_file_obj, f"{remote_path}{f}/",
                _files, exclude
            )
            continue
        scp_client_obj.get(f"{remote_path}{f}", f"{BACKUP_PATH}{f}")
        zip_file_obj.write(f"{BACKUP_PATH}{f}", f"{remote_path[1:]}{f}")
        remove(f"{BACKUP_PATH}{f}")
    return zip_file_obj


def exclude_files_and_dirctories(exclude: list, _list: list):
    for e in exclude:
        if e in _list:
            _list.remove(e)


def db_backup(ssh: paramiko.SSHClient, db_type: str, db_user: str, db_password: str,
              db_container_name: str, database_name: str, path: str):
    if db_type not in ("mysql", "mariadb"):
        return

    dump_binary = "mysqldump" if db_type == "mysql" else "mariadb-dump"
    cmd = (
        f'docker exec {db_container_name} {dump_binary} -u {db_user} '
        f'--password={db_password} {database_name} > "{path}/{database_name}.sql"'
    )
    stdin, stdout, stderr = ssh.exec_command(cmd)
    if stderr:
        logging.error(stderr.read().decode().strip())


def create_zipFile(hostname, port, username, password, var_files, opt_files,
                   db_type, exclude, db_user: str, db_password: str,
                   db_container_name: str, database_name: str):
    ssh = None
    try:
        ssh = createSSHClient(hostname, port, username, password)
        with (
            SCPClient(ssh.get_transport()) as scp,
            zipfile.ZipFile(BACKUP_FILE_NAME, "w", zipfile.ZIP_DEFLATED) as zf
        ):
            if db_type in ("mysql", "mariadb"):
                db_backup(ssh, db_type, db_user, db_password,
                          db_container_name, database_name, var_files)
            remote_var_files = get_list_dir(ssh, var_files)
            remote_opt_files = get_list_dir(ssh, opt_files)
            exclude_files_and_dirctories(exclude, remote_var_files)
            exclude_files_and_dirctories(exclude, remote_opt_files)

            zf = _create_zipFile(
                ssh, scp,
                zf, var_files,
                remote_var_files, exclude
            )
            zf = _create_zipFile(
                ssh, scp,
                zf, opt_files,
                remote_opt_files, exclude
            )

    except Exception as e:
        logging.info(e)
        if ssh and hasattr(ssh, "close"):
            ssh.close()
        return
    ssh.close()
    return BACKUP_FILE_NAME


def createSSHClient(server, port, user, password):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(server, port, user, password)
    return client


def split_file(file_path: str, max_size: int = MAX_PART_SIZE) -> List[str]:
    """Split file into parts not exceeding ``max_size`` bytes."""

    parts = []
    part_num = 1
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(max_size)
            if not chunk:
                break
            part_name = path.join(
                PARTS_PATH, f"{path.basename(file_path)}.part{part_num}"
            )
            with open(part_name, "wb") as pf:
                pf.write(chunk)
            parts.append(part_name)
            part_num += 1

    return parts


async def send_full_backups():
    for i in SERVER_LIST["servers"]:
        hostname = i["host"]
        port = i["port"]
        username = i["user"]
        password = i["pass"]
        db_type = i.get("db_type")
        if not db_type and i.get("is_mysql_DB"):
            db_type = "mysql"
        exclude = i["exclude"]
        db_user = i.get("db_user", i.get("mysql_user"))
        db_password = i.get("db_password", i.get("mysql_password"))
        database_name = i["database_name"]
        db_container_name = i.get("db_contaner_name", i.get("mysql_contaner_name"))
        var_files = i["var_files"]
        opt_files = i["opt_files"]
        bac = create_zipFile(
            hostname,
            port,
            username,
            password,
            var_files,
            opt_files,
            db_type,
            exclude,
            db_user,
            db_password,
            db_container_name,
            database_name,
        )
        if not bac:
            continue
        date = get_date()
        if path.getsize(bac) > MAX_PART_SIZE:
            parts = split_file(bac, MAX_PART_SIZE)
            remove(bac)
            for idx, part in enumerate(parts, start=1):
                await BOT.send_document(
                    chat_id=CHAT_ID,
                    document=types.FSInputFile(path=part, filename=path.basename(part)),
                    caption=(
                        f'🕐 Date : {date}\n\n🔰 IP : `{hostname}`\n'
                        f'Part {idx}/{len(parts)}'
                    ),
                )
                remove(part)
        else:
            await BOT.send_document(
                chat_id=CHAT_ID,
                document=types.FSInputFile(path=bac, filename=bac),
                caption=f'🕐 Date : {date}\n\n🔰 IP : `{hostname}`'
            )
            remove(bac)


async def main() -> None:
    asc = AsyncIOScheduler(timezone=TZ)
    minute, hour, day, month, day_of_week = CRON_JOB.split()
    asc.add_job(func=send_full_backups, trigger="cron",
                minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week)
    asc.start()
    await dp.start_polling(BOT)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
