#!/usr/local/bin/python

# Script to batch unarchive channels in case you accidentally archived lots of channels that shouldn't be archived..
# Usage: python batch-unarchive.py [channel_name_list.txt]
# channel_name_list.txt should be a file that contains a list of channel names, one line per channel

from datetime import timedelta, datetime
from time import sleep
import os
import sys
import requests


SLACK_TOKEN      = os.getenv('SLACK_TOKEN')

def get_all_channels():
  payload  = {'exclude_archived': 0, 'exclude_members': 1}
  api_endpoint = 'channels.list'
  channels = slack_api_http_get(api_endpoint=api_endpoint, payload=payload)['channels']
  all_channels = []
  for channel in channels:
    all_channels.append({'id': channel['id'], 'name': channel['name'], 'created': channel['created']})
  return all_channels

# api_endpoint is a string, and payload is a dict
def slack_api_http_get(api_endpoint=None, payload=None):
  uri = 'https://slack.com/api/' + api_endpoint
  payload['token'] = SLACK_TOKEN
  try:
    attempts = 0
    while attempts < 3:
        response = requests.get(uri, params=payload)
        if response.status_code == requests.codes.ok:
          return response.json()
        elif response.status_code == requests.codes.too_many_requests:
          # print "sleep %s seconds for API rate limit" % response.headers['Retry-After'];
          attempts += 1;
          sleep(int(response.headers['Retry-After']));
        else:
          raise Exception(response.content)
      
  except Exception as e:
    raise Exception(e)


def unarchive_channels(channels):
  print "Unarchive channels..."
  api_endpoint = 'channels.unarchive'
  for channel in channels:
    payload = {'channel': channel['id']}
    slack_api_http_get(api_endpoint=api_endpoint, payload=payload)

    print "Unarchiving channel... %s" % channel['name'].encode('utf8', 'replace')

with open(sys.argv[1]) as f:
    channel_to_unarchive_names = f.readlines()

channel_to_unarchive_names = [x.strip() for x in channel_to_unarchive_names] 
print channel_to_unarchive_names
all_channels = get_all_channels()
channels_to_unarchive = filter(lambda c: c['name'] in channel_to_unarchive_names, all_channels)
print channels_to_unarchive
unarchive_channels(channels_to_unarchive)

