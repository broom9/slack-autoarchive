#!/usr/local/bin/python
# -*- coding: utf-8 -*-


from datetime import timedelta, datetime
from time import sleep
import os
import sys
import requests

reload(sys)  
sys.setdefaultencoding('utf8')

#
# This will archive inactive channels. The inactive period is in days as 'DAYS_INACTIVE'
# You can put this in a cron job to run daily to do slack cleanup.
#

SLACK_TOKEN      = os.getenv('SLACK_TOKEN')
DAYS_INACTIVE    = int(os.getenv('DAYS_INACTIVE', 60))
TOO_OLD_DATETIME = datetime.now() - timedelta(days=DAYS_INACTIVE)
DRY_RUN = (os.getenv('DRY_RUN', "true") == "true")
ADMIN_CHANNEL = os.getenv('ADMIN_CHANNEL')
WHITELIST_KEYWORDS = os.getenv('WHITELIST_KEYWORDS')


# api_endpoint is a string, and payload is a dict
def slack_api_http_get(api_endpoint=None, payload=None):
  uri = 'https://slack.com/api/' + api_endpoint
  payload['token'] = SLACK_TOKEN
  try:
    attempts = 0
    while attempts < 3:
        response = requests.get(uri, params=payload)
        if response.status_code == requests.codes.ok and response.json()['ok']:
          return response.json()
        elif response.status_code == requests.codes.too_many_requests:
          # print "sleep %s seconds for API rate limit" % response.headers['Retry-After'];
          attempts += 1;
          sleep(int(response.headers['Retry-After']));
        else:
          raise Exception(response.content)
      
  except Exception as e:
    raise Exception(e)


# too_old_datetime is a datetime object
def get_all_channels():
  payload  = {'exclude_archived': 1}
  api_endpoint = 'channels.list'
  resp_json = slack_api_http_get(api_endpoint=api_endpoint, payload=payload)
  try:
    channels = resp_json['channels']
    all_channels = []
    for channel in channels:
        all_channels.append({'id': channel['id'], 'name': channel['name'], 'created': channel['created']})
    return all_channels
  except Exception as e:
    print resp_json
    raise Exception(e)


def get_last_message_timestamp(channel_history, too_old_datetime):
  last_message_datetime = too_old_datetime
  for message in channel_history['messages']:
    if 'subtype' not in message or message['subtype'] == 'file_share' or message['subtype'] == 'file_comment':
      last_message_datetime = datetime.fromtimestamp(float(message['ts']))
      break
  return last_message_datetime


def get_inactive_channels(all_unarchived_channels, too_old_datetime):
  print "Find inactive channels..."
  payload  = {'inclusive': 0, 'oldest': 0, 'count': 50}
  api_endpoint = 'channels.history'
  inactive_channels = []
  for channel in all_unarchived_channels:
    sys.stdout.write('.')
    sys.stdout.flush()
    payload['channel'] = channel['id']
    channel_history = slack_api_http_get(api_endpoint=api_endpoint, payload=payload)
    last_message_datetime = get_last_message_timestamp(channel_history, datetime.fromtimestamp(float(channel['created'])))
    members = slack_api_http_get(api_endpoint="conversations.members", payload={'channel': channel['id'], 'limit': 20})['members']
    if len(members) == 0:
        print "Channel %s is inactive because of zero members" % channel['name']
        inactive_channels.append(channel)
    elif last_message_datetime <= too_old_datetime:
        if not (len(filter(lambda x: datetime.fromtimestamp(float(x['ts'])) >= too_old_datetime, channel_history['messages'])) > 10 and len(members) > 5):
            print "Channel %s is inactive because the latest human message is older than %s" % (channel['name'], too_old_datetime)
            inactive_channels.append(channel)
  return inactive_channels

def filter_out_whitelist_channels(inactive_channels):
    channels_to_archive = []
    for channel in inactive_channels:
      whitelisted = False
      if WHITELIST_KEYWORDS:
        for kw in WHITELIST_KEYWORDS.split(","):
          if kw in channel['name']:
            whitelisted = True
      if not whitelisted:
        channels_to_archive.append(channel)
    return channels_to_archive

def send_channel_message(channel_id, message):
  payload  = {'channel': channel_id, 'username': 'channel_reaper', 'icon_emoji': ':ghost:', 'text': message}
  api_endpoint = 'chat.postMessage'
  slack_api_http_get(api_endpoint=api_endpoint, payload=payload)


def archive_inactive_channels(channels):
  print "Archive inactive channels..."
  api_endpoint = 'channels.archive'
  for channel in channels:
    if not DRY_RUN:
      message = "This channel has had no activity for %s days. It is being auto-archived." % DAYS_INACTIVE
      message += " If you feel this is a mistake you can unarchive this channel by clicking the link below to bring it back at any point."
      send_channel_message(channel['id'], message)
      if ADMIN_CHANNEL:
        send_channel_message(ADMIN_CHANNEL, "Archiving channel... %s" % channel['name'])
      payload = {'channel': channel['id']}
      slack_api_http_get(api_endpoint=api_endpoint, payload=payload)

    print "Archiving channel... %s" % channel['name'].encode('utf8', 'replace')

if DRY_RUN:
  print "THIS IS A DRY RUN. NO CHANNELS ARE ACTUALLY ARCHIVED."
all_unarchived_channels = get_all_channels()
inactive_channels       = get_inactive_channels(all_unarchived_channels, TOO_OLD_DATETIME)
channels_to_archive = filter_out_whitelist_channels(inactive_channels)
print "Channels to archive:"
for c in channels_to_archive:
    print c["name"]
archive_inactive_channels(channels_to_archive)

