# Welcome to the home page for Wes McCauley the Discord Bot
This bot was first developed for use in the [OldTimeHockey](http://www.roldtimehockey.com) Discord Server. All of the code in this repository is deployed by SPRX97. If you are interested in contributing or re-purposing, feel free to contact me on Discord (sprx97), [Reddit](http://www.reddit.com/u/sprx97), or [Github](http://www.github.com/Spartan97).

# Notes
- Python 3.8+ is required
- Non-exaustive list of pip installs: discord.py 1.5.1+, pickle 0.7.5+, pymysql 1.0.2+ TODO: This needs to be updated
- The database is a standard mysql installation
- Everything is deployed from a DigitalOcean droplet running Ubuntu 20.04 x64 (soon to be upgraded to 24.04)
- The droplet takes weekly backups in case of catastrophic failure
- Process is managed using pm2

# Restart Wes
- `sudo pm2 start DiscordBot_v2.py --interpreter=python3`
- `sudo pm2 (re)start <pm2 Process ID>`
- pm2 process ID found via `sudo pm2 list`

# Adding the bot to Discord
- Currently the bot is private, meaning only I can add it to servers, but if it ever goes public, the following invite link would ensure the correct permissions:
  - https://discord.com/oauth2/authorize?client_id=250826109216620545&scope=bot&permissions=326686288912
