import poplib
import email

import urllib2 # url reading
from lxml import etree
from lxml import html # xml parsing

import sys
sys.path.append("../")
import Config

def checkFleaflickerTrades():
	pass

# Old method from when Fleaflicker included the non-player commish on trade emalis.
# Can probably remove once hte new method is working.
def checkEmails():
	pop_conn = poplib.POP3_SSL("pop.gmail.com", 995)
	pop_conn.user(Config.config["email_username"])
	pop_conn.pass_(Config.config["email_password"])

	stringsToAnnounce = []

	num_msgs = len(pop_conn.list()[1])
	for i in range(num_msgs):
		body = to = frm = subject = ""
		for j in pop_conn.retr(i+1)[1]:
			msg = email.message_from_bytes(j)
			if msg['to'] != None:
				to = msg['To']
			if msg['from'] != None:
				frm = msg['From']
			if msg['subject'] != None:
				subject = msg['Subject']
			if msg.get_payload() and type(msg.get_payload()) != list:
				body += msg.get_payload() + "\n"

		# only return FF emails
		if "info+noreply@fleaflicker.com" in frm:
			try:
				start = body.index("Please visit https://www.fleaflicker.com/nhl")
				end = body.index("Thanks,\nThe Fleaflicker Team")
				stringsToAnnounce.append(body[start:end])
			except:
				print("Non-FF email received and ignored.")

# comment this out for debugging
# quitting commits all changes and removes all "popped" emails from the queue
	pop_conn.quit()

	return stringsToAnnounce

if __name__ == "__main__":
	strs = checkEmails()
	for s in strs:
		print(s)
