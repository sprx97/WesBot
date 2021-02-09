# Welcome to the home page for Wes McCauley the Discord Bot
This bot was first developed for use in the [OldTimeHockey](http://www.roldtimehockey.com) Discord Server. All of the code in this repository is deployed by Spartan97/SPRX97. If you are interested in contributing or re-purposing, feel free to contact me on Discord (SPRX97#9662), [Reddit](http://www.reddit.com/u/sprx97), or [Github](http://www.github.com/Spartan97).

# Notes
- Python 3.8+ is required
- Non-exaustive list of pip installs: discord.py 1.5.1+, pickle 0.7.5+, pymysql 1.0.2+
- The database is a standard mysql installation
- Everything is deployed from a DigitalOcean droplet running Ubuntu 18.04 x64 (soon to be upgraded to 20.04)
- The droplet takes weekly backups in case of catastrophic failure
- Process is managed using pm2

# Restart Wes
- `sudo pm2 start DiscordBot_v2.py --interpreter=python3`
- `sudo pm2 (re)start <pm2 Process ID>`
- pm2 process ID found via `sudo pm2 list`
