# Vendor UI vs the native image: gap table

Every command the stock web UI sends to `cgi-bin/http.cgi` ([vendor-command-map.md](vendor-command-map.md), 198 commands),
the native equivalent, and what is left. Issue #308. Status 2026-11-14.

Native column:
- **OpenWrt**: standard OpenWrt/LuCI does it (the package may need `opkg install`; this table does not verify what the image ships).
- **ours**: an `x28-*` package does it.
- **none**: nothing yet; the Issue column says where it is tracked.
- **drop**: the vendor feature has no use on this image (reason given).

Priority is the one on the follow-up issue. Nothing here was run on a unit; the table comes from the UI code, the strings
of `http.cgi` (it shells out to `iptables`, `vpn_mgr`, `fota_start.sh`, `tzupdate`, `locknet.sh`, `sms_send`, and tools such as
`listplmn`, `enablepin`/`disablepin`/`changepin`/`unlockpin`, `writeimei`, `sendat`, `cwmpd`) and the project's own notes.

## Cellular

| Commands | Purpose | Native | Priority / Issue |
|---|---|---|---|
| `APN_CONFIG`, `APN_INFO_PROCESS` | one APN, IP type | ours (`x28_mipc`, `x28-apn`, APN from SIM or manual) | done (#125) |
| `MULTI_APN_INFO`, `MAIN_APN_MOVE_MULTI_APN` | several bearers | none | P2 #581 |
| `IP_PASSTHROUGH`, `MULTI_IP_PASSTHROUGH` | give the WAN IP to one LAN host | none | P2 #581 |
| `LOCK_BAND` | 4G/5G band lock | ours for NR masks (`x28-nrband`); 4G none | P0 #304 |
| `PCI_LOCK_ENABLE`, `PCI_SCAN` | PCI lock and scan | none | P0 #305 |
| `LOCK_PHY_CELL`, `LOCK_PLMN` | cell and PLMN lock | none | P0 #306 |
| `NETWORKSET_MODE`, `NETWORKSET_MODE_MT2731`, `RESCAN_NETWORK`, `SCCAN_PLMN` | network mode, rescan, manual registration | ours: `x28-plmn-scan` only | P0 #307 |
| `DATA_ROAMING`, `FLIGHT_MODE_INFO`, `DATA_SWITCH`, `AUTO_DIAL` | roaming, flight mode, data on/off | none (netifd `ifup/ifdown` only) | P2 #580 |
| `UNLOCK_SIM`, `QUERY_SIM_STATUS`, `MODEM_CMD` | SIM PIN/PUK | none | P2 #579 |
| `SEND_AT`, `USSD_SEND`, `GET_NEIGHBOR_INFO`, `GET_ENDC_INFO`, `GET_MOUNT_INFO`, `LTE_CALIBRATION`, `NR_CALIBRATION`, `WCDMA_CALIBRATION`, `NR_RSRP_THRESHOLD`, `SYS_INFO_NETWORK` | AT console, USSD, cell and calibration info | ours: `x28-modem-status` (signal); rest none | P2 #582 |
| `CHANGE_CARD_TYPE`, `GET_ESIM_INFO`, `DOWNLOAD_ESIM_INFO`, `RESET_ESIM_INFO`, `ESIM_URL_SETTING`, `SLICE_CONIFIG`, `UE_CONFIG`, `CHANGE_ANTENNA_STATUS` | eSIM, SIM switch, slicing, UE config, antenna | none | P3 #586 |
| `SLEEP_SETTINGS`, `TRAFFIC_LIMIT_SETTING` | auto dormant, monthly limit | none | P3 #584 |

## Voice, SMS, phone book

| Commands | Purpose | Native | Priority / Issue |
|---|---|---|---|
| `SMS_INFO`, `SMS_SEND`, `SMS_DELETE`, `SMS_SETTING` | SMS inbox, outbox, send, settings | ours (`x28-telephony`, LuCI pages, HTTP API) | done (#309, #15) |
| `GET_PHONE_BOOK`, `SET_PHONE_BOOK`, `DEL_PHONE_BOOK` | phone book | ours (`x28-telephony`) | done |
| `VOICE_BASIC_CONFIG`, `VOICE_ADVANCE_CONFIG`, `VOIP_ADVANCED_CONFIG`, `VOIP_CALL_CIPHER`, `SIP_ALG` | voice, SIP, VoLTE | none | P2 #16, #17 |

## Network, LAN, WAN

| Commands | Purpose | Native | Priority / Issue |
|---|---|---|---|
| `NETWORK_CONFIG`, `MUTIL_NETWORK_CONFIG`, `LAN_INFO`, `STATIC_LEASE`, `IP_MAC_BINDING`, `APPLY_FILTER`, `DHCPCLIENT_INFO` | LAN address, DHCP, static leases | OpenWrt (netifd, dnsmasq; `x28-dhcp` guard) | done |
| `MUTIL_VLAN_CONFIG`, `NETWORKMODE_SWITCH`, `WAN_WLAN_MODE`, `BROADBAND_SETTING`, `MULTI_WAN_SETTING`, `MULTI_WAN_INFO`, `MULTI_WIRED_WAN_INFO`, `WAN_MAC_GET`, `WAN_MAC_SETTINGS`, `WAN_LINK_DETECT_SETTING`, `ROUTER_INFO`, `ROUTER_TABLE` | VLAN, wired WAN, multi-WAN, WAN MAC, routes | OpenWrt (LuCI network, `mwan3` optional; `x28-switch`) | done, tracked by #164 |
| `SET_ARP_AGING`, `ARP_BINDING` | ARP aging and binding | OpenWrt (sysctl, `/etc/ethers`) | P3, no issue |
| `DDNS_DATA` | dynamic DNS | OpenWrt (`ddns-scripts`) | P3, no issue |
| `SET_DATETIME`, `SYNC_CLIENT_TIME`, `DST_SETTING` | time, NTP, DST | OpenWrt (`sysntpd`, zone); NTP default was #169 | done |
| `IPSEC_CONFIG`, `VPN_CONFIG`, `VPN_ONLY_ONE`, `GRE_SETTING`, `L2TPV3_CONFIG`, `GET_L2TPV3_STATUS`, `VXLAN_SETTING` | VPN and tunnels | OpenWrt packages (openvpn, strongswan, gre, l2tp, vxlan); VPN set in the image (#230); testing #229 | P2 #229 |
| `PORTAL_AUTHENTICATION` | captive portal | OpenWrt (`nodogsplash`, installable) | P3, no issue |
| `GET_WEB_LIST`, `SET_WEB_LIST`, `GET_PING_LIST`, `SET_PING_LIST`, `REMOTE_WEBPORT_SETTING` | remote login allow list, WAN ping, web port | OpenWrt (firewall rules, uhttpd listen) | done |
| `NETWORK_TOOLS`, `REMOTE_PACKET_CAPTURE` | ping, traceroute, tcpdump | OpenWrt (LuCI diagnostics; `tcpdump` installable) | done |

## Firewall and traffic

| Commands | Purpose | Native | Priority / Issue |
|---|---|---|---|
| `FW_SWITCH_SETTING`, `DEFAULT_FILTER`, `MAC_FILTER`, `MAC_DEFAULT_FILTER`, `PORT_FILTER`, `IP_PORT_FILTER`, `URL_FILTER`, `URL_DEFAULT_FILTER`, `OTHER_FILTER`, `FIRWALL_ACL_FILTER`, `FW_ACCESS_CONTROL_SIMPLE`, `GET_SYSTEM_PORT` | filters and port forwards | OpenWrt (fw3, LuCI firewall); URL filter needs a package | done, LuCI page tracked by #164 |
| `NETWORK_SERVICE` | DMZ | OpenWrt (fw3 redirect/DMZ) | done |
| `FW_UPNP_STATUS` | UPnP | OpenWrt (`miniupnpd`, installable) | P3, no issue |
| `DDOS_PROTECTION` | flood protection | OpenWrt (fw3 `syn_flood`) | done |
| `SPEED_LIMIT`, `PARENT_MODEL`, `PARENTAL_CONTROL_SPEED`, `PARENTAL_CONTROL_TIME`, `PARENTAL_CONTROL_URL`, `GETGLOBESTATUS` | per-host speed, parental control | OpenWrt (`sqm`, fw3 time rules) | P3, no issue |
| `GAME_TRAFFIC_ACCELERATION` | traffic priority | OpenWrt (`sqm`/QoS) | P3 #587 |
| `TRAFFIC_SETTING`, `TRAFFIC_DAY_STAT`, `TRAFFIC_HOUR_STAT`, `TRAFFIC_INTERFACE_LIST` | traffic statistics | OpenWrt (`vnstat`, `nlbwmon`, installable) | P3 #584 |

## Wi-Fi

| Commands | Purpose | Native | Priority / Issue |
|---|---|---|---|
| `WIRELESS_CONFIG`, `WIRELESS5G_CONFIG`, `WIFI_INIT_STATUS`, `WIFI24G_LIST_INFO`, `WIFI5G_LIST_INFO` | SSIDs, security, client list | ours (`x28-wifi`, stock LuCI); testing #150 | done, test open |
| `WIRELESS_MACFILTER`, `WIRELESS_POWER`, `WLAN_5G_TPC`, `WIRELESS_ADVANCE`, `WIRELESS5G_ADVANCE`, `WIFI_SCHEDULE_SETTING` | MAC filter, power, advanced, schedule | partly (UCI options); not checked on the unit | P2 #583 |
| `WPS_CONFIG`, `WPS_PIN_CODE`, `OPEN_RANDOM_PIN`, `SET_WPS_SUCCESS_FLAG` | WPS | ours (`x28-wps`) | done |
| `NFC_SETTING`, `MESH_SETTING`, `NETWORK_TOPOLOPY` | NFC pairing, mesh | none; hardware unconfirmed | P3 #587 |
| `RESET_FIRST_LOGIN_FLAG` | first-login wizard | drop: LuCI sets the password at first login | none |

## System and management

| Commands | Purpose | Native | Priority / Issue |
|---|---|---|---|
| `LOGIN`, `LOGOUT`, `CHANGE_PASSWD`, `CHANGE_USERNAME`, `CHANGE_LANGUAGE`, `GET_NEXT_LOGIN_TIME`, `INIT_PAGE`, `GET_STATUS_BAR`, `GET_SYS_STATUS`, `GET_DASHBOARD_INDEX`, `DEVICE_INFO`, `DEVICE_VERSION_INFO` | login, status pages | OpenWrt (LuCI, rpcd) | done |
| `SYS_REBOOT`, `TIME_TO_RESTART`, `UNORMAL_REBOOT_SWITCH` | reboot, scheduled restart | OpenWrt (LuCI reboot, cron) | P3 #584 |
| `RESTORE_DEFAULT` | factory reset | ours (button and LuCI, PR #552) | merged, test open (#551) |
| `CONFIG_EXPORT`, `CONFIG_LOADER`, `CONFIG_UPDATE`, `SYS_UPDATE`, `UPDATE_PARTIAL` | backup, restore, flash | ours (sysupgrade, signed images, LuCI flash page #478) | done |
| `SYS_AUTO_UPGRADE`, `DETECTION_VERSION_INFO`, `UPGRADE_IMMEDIATELY`, `ONLINE_UPGRADE_AUTO`, `FOTA_SETTINGS_NEW` | online upgrade | ours (`x28-update`, `x28-upgrade`) | done |
| `SYS_SSH_SET`, `SYS_SERVICE_SET`, `ADB_SWITCH` | SSH, services, ADB | OpenWrt (dropbear, init); ADB: drop, no adbd on the image | done |
| `SYS_LOG`, `LOG_INFO`, `EXPORT_LOG`, `EXPORT_HWSECURITY_LOG`, `COMMLOG_BACKUP_TIME`, `MODEM_LOG_SWITCH`, `DEVICE_SELF_CHECK` | logs, self check | OpenWrt (logread, LuCI); `MODEM_LOG_SWITCH` is the RIL log spam (#9) | P3 #9 |
| `LIGHTS_OUT_SETTING`, `DISPLAY_SOLUTION_MODE` | LEDs off at night, LED mode | ours (`x28-leds`); schedule none | P3 #584 |
| `CONTROLS_WARM` | thermal control | ours (docs/THERMAL.md); fan control #47 | P3 #47 |

## Carrier, industrial, remote management

| Commands | Purpose | Native | Priority / Issue |
|---|---|---|---|
| `TR069_CONFIG`, `TR369_CONFIG`, `TR069_LOG_SWITCH`, `SNMP_SETTING`, `DM_SETTING`, `TELECOM_DM`, `LINKDM_SETTING`, `MQTT_CONFIG`, `MQTT_SETTING`, `ONENET_SETTING` | carrier and cloud management | SNMP and MQTT: OpenWrt packages; TR-069 and DM clients: vendor only | P3 #585 |
| `SERIAL_SETTING`, `SERIAL_DATA_OPER`, `INDUSTRY_NETWORK_SET`, `MODBUS_SLAVE_SET`, `MODBUS_SLAVE_MODULE_SET`, `MODBUS_SLAVE_SERIAL_DATA_DEBUG`, `DIDO_SETTING`, `SFP_IPA_SETTING`, `GET_IPTV_SETTINGS`, `SET_IPTV_SETTINGS` | industrial ports, SFP, IPTV | none; may not exist on this board | P3 #587 |

## Not yet studied

The UI shows a command, not what runs behind it. This pass read only the UI code and the `http.cgi` strings. The stock slot B
rootfs and the NAND backup were not opened, so the AT and mipc calls behind each cellular command are still to be found; each
cellular issue above starts with that read-only step.
