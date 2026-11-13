#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# HTTP API of x28-telephony: GET and POST /cgi-bin/x28-telephony/messages with "Authorization: Bearer <API key>".
exec /usr/sbin/x28-sms cgi
