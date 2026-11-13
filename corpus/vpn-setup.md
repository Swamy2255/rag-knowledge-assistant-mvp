---
title: Setting Up VPN Access
owner: IT Support — Network Team
last_updated: 2026-10-02
doc_id: DOC-002
---

# Setting Up VPN Access

## First-time setup

Install the company VPN client from the Software Center (Windows) or Self Service (Mac). The client is called "Company VPN". After installation, open the client and enter the server address vpn.company.example. Sign in with your company username and password, then approve the MFA prompt on your phone.

## Connecting from home

Open the VPN client and click Connect. You must be on VPN to reach internal tools such as the ticketing system, the file shares, and the internal wiki. If you only need email and chat, VPN is not required.

## Troubleshooting connection failures

If the client shows "Connection failed", first check that your internet connection works by opening any public website. Then confirm your password is current — a recently changed password is the most common cause. If the client shows "Certificate error", your laptop certificate may have expired; contact the Help Desk to re-issue it. If the client connects but internal sites do not load, try disconnecting and reconnecting once, then restart the client.

## VPN and multi-factor authentication

Every new VPN connection requires MFA approval. If you do not receive the MFA prompt, check that notifications are enabled for the Authenticator app and that your phone has a data connection. Approving from a smartwatch is not supported.
