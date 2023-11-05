# Marzban-backup
a simple bot for get full backup of Marzban pannel

this bot use ssh to download all files from the server so it can be use on iran serveers

## How to run

first clone the project 

```bash
git clone https://github.com/ImMohammad20000/marzban-backup.git && cd marzban-backup
```

now create `.env` file and configure it.

```bash
mv .env.example .env
```

```bash
nano .env
```

1. set `BOT_TOKEN` to your bot's API Token
2. set `CHAT_ID` to your Telegram account's numeric ID, you can get your ID from [@userinfobot](https://t.me/userinfobot)
3. if you want to use proxy for connect to telegram uncomment `PROXY_URL` and set a socks5 or http proxy 
4. set `TZ` to your time zone, by default set to `Asia/Tehran`
5. `CRON_JOB` use to schedule send backups, by default send backups every hour [moore info](https://crontab.guru/examples.html)

then save the changes

It's time to create `server_list.json` file and configure oure ssh login info 

```bash
mv server_list.json.example server_list.json
```

```bash
nano server_list.json
```

```json
{
  "servers": [
    {
      "host": "host",
      "port": 22,
      "user": "user",
      "pass": "pass",
      "is_mysql_DB": false,
      "mysql_db_path": "/var/lib/marzban/mysql/marzban/",
      "exclude": [
        "mysql"
      ],
      "var_files": "/var/lib/marzban/",
      "opt_files": "/opt/marzban/"
    }
  ]
}
```

if you use **mysql** database for your pannel set `"is_mysql_DB"` flag `true`

if you don't want get backup of some folders or files use `exclude` list

bot support multiple panel if you have another panel you can use this json

```json
{
  "servers": [
    {
      "host": "host",
      "port": 22,
      "user": "user",
      "pass": "pass",
      "is_mysql_DB": false,
      "mysql_db_path": "/var/lib/marzban/mysql/marzban/",
      "exclude": [
        "mysql"
      ],
      "var_files": "/var/lib/marzban/",
      "opt_files": "/opt/marzban/"
    },
    {
      "host": "host2",
      "port": 22,
      "user": "user2",
      "pass": "pass2",
      "is_mysql_DB": true,
      "mysql_db_path": "/var/lib/marzban/mysql/marzban/",
      "exclude": [
        "mysql"
      ],
      "var_files": "/var/lib/marzban/",
      "opt_files": "/opt/marzban/"
    }
  ]
}
```

then save the changes

now run this command for start bot


```bash
docker compose up -d
```

to test bot use `/backup` command

## Modify .env or json files

if you want to edit `.env` or `server_list.json` after you save changes **you have to** use `docker compose down` and `docker compose up --build -d` for re-build docker contaner

## Update

to update the project just clone the repository again.
