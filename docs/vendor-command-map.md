# Vendor UI -> backend command map

Generated from vendor-ui/js. All calls are JSON POSTs to `cgi-bin/http.cgi` with `{cmd:<id>, method:..., ...}`.


## .

- `home.js`: CHANGE_LANGUAGE(97), GET_STATUS_BAR(394), GET_SYS_STATUS(113), INIT_PAGE(80), LOGOUT(101), MODEM_CMD(51), QUERY_SIM_STATUS(134), SYS_REBOOT(6), UNLOCK_SIM(340)
- `index.js`: CHANGE_PASSWD(102), INIT_PAGE(80), LOGOUT(101), RESET_FIRST_LOGIN_FLAG(499)
- `info.js`: DEVICE_VERSION_INFO(43)
- `login.js`: CHANGE_LANGUAGE(97), GET_NEXT_LOGIN_TIME(232), GET_SYS_STATUS(113), INIT_PAGE(80), LOGIN(100)
- `step.js`: RESET_FIRST_LOGIN_FLAG(499), WIRELESS5G_CONFIG(211), WIRELESS_CONFIG(2)

## advance

- `alg.js`: SIP_ALG(426)
- `arpTime.js`: SET_ARP_AGING(258)
- `autoDial.js`: AUTO_DIAL(222), DATA_SWITCH(227)
- `autoDormant.js`: SLEEP_SETTINGS(371)
- `dataSwitch.js`: DATA_SWITCH(227)
- `ddns.js`: DDNS_DATA(221)
- `displaySolutionMode.js`: DISPLAY_SOLUTION_MODE(235)
- `dmPlatform.js`: DM_SETTING(257)
- `esimManage.js`: DOWNLOAD_ESIM_INFO(250), ESIM_URL_SETTING(261), GET_ESIM_INFO(247), RESET_ESIM_INFO(249)
- `gre.js`: GRE_SETTING(260), VPN_ONLY_ONE(425)
- `ipPass.js`: IP_PASSTHROUGH(251)
- `ipPassMulti.js`: MULTI_IP_PASSTHROUGH(458)
- `iptv.js`: GET_IPTV_SETTINGS(?), SET_IPTV_SETTINGS(?)
- `l2tpv3.js`: GET_L2TPV3_STATUS(398), L2TPV3_CONFIG(279), VPN_ONLY_ONE(425)
- `linkDM.js`: LINKDM_SETTING(339)
- `lockBand.js`: LOCK_BAND(161)
- `lockPhyCell.js`: LOCK_PHY_CELL(160)
- `lockPlmn.js`: LOCK_PLMN(219)
- `mqttSettings.js`: MQTT_CONFIG(299)
- `multiWan.js`: MULTI_WAN_SETTING(496)
- `netChange.js`: BROADBAND_SETTING(302), LAN_INFO(208), NETWORKMODE_SWITCH(277), SFP_IPA_SETTING(255), WAN_WLAN_MODE(285)
- `networkConfig.js`: AUTO_DIAL(222), DATA_ROAMING(220), FLIGHT_MODE_INFO(226), NETWORKSET_MODE(218), RESCAN_NETWORK(288)
- `networkSet.js`: NETWORKSET_MODE_MT2731(256), SCCAN_PLMN(228)
- `onenet.js`: ONENET_SETTING(252)
- `otherConfig.js`: NR_RSRP_THRESHOLD(293)
- `pciLock.js`: PCI_LOCK_ENABLE(341), PCI_SCAN(342)
- `pinSet.js`: GET_SYS_STATUS(113), MODEM_CMD(51), QUERY_SIM_STATUS(134)
- `portalSetting.js`: PORTAL_AUTHENTICATION(468)
- `remoteLogin.js`: GET_WEB_LIST(?), SET_WEB_LIST(?)
- `remotePin.js`: GET_PING_LIST(?), SET_PING_LIST(?)
- `roaming.js`: DATA_ROAMING(220)
- `route.js`: LAN_INFO(208), ROUTER_TABLE(164)
- `sccan_plmn.js`: SCCAN_PLMN(228)
- `simChange.js`: CHANGE_CARD_TYPE(246)
- `sliceConfiguration.js`: SLICE_CONIFIG(254)
- `snmpSetting.js`: SNMP_SETTING(344)
- `staticIp.js`: APPLY_FILTER(20), IP_MAC_BINDING(24), NETWORK_CONFIG(3), STATIC_LEASE(115)
- `telecomDM.js`: TELECOM_DM(271)
- `tr069.js`: TR069_CONFIG(212)
- `tr369.js`: TR369_CONFIG(482)
- `ueConfig.js`: UE_CONFIG(287)
- `unclok.js`: UNLOCK_SIM(340)
- `vpn.js`: VPN_CONFIG(272), VPN_ONLY_ONE(425)
- `vxlanSetting.js`: VPN_ONLY_ONE(425), VXLAN_SETTING(332)
- `wanSettings.js`: WAN_MAC_GET(?), WAN_MAC_SETTINGS(?)
- `wiredSetting.js`: BROADBAND_SETTING(302)

## config

- `controlsWarm.js`: CONTROLS_WARM(372)
- `dhcpSetting.js`: APPLY_FILTER(20), IP_MAC_BINDING(24), NETWORK_CONFIG(3), STATIC_LEASE(115)
- `dhcpSettingMulti.js`: MUTIL_NETWORK_CONFIG(289)
- `main5gWifiSetting.js`: NFC_SETTING(376), WIFI_INIT_STATUS(417), WIRELESS5G_CONFIG(211)
- `mainWifiSetting.js`: DEVICE_INFO(207), NFC_SETTING(376), WIFI_INIT_STATUS(417), WIRELESS_CONFIG(2)
- `nfc.js`: NFC_SETTING(376)
- `setting_24wifi_1.js`: WIFI_INIT_STATUS(417), WIRELESS_CONFIG(2)
- `setting_24wifi_2.js`: WIFI_INIT_STATUS(417), WIRELESS_CONFIG(2)
- `setting_24wifi_3.js`: WIFI_INIT_STATUS(417), WIRELESS_CONFIG(2)
- `setting_24wifi_4.js`: WIFI_INIT_STATUS(417), WIRELESS_CONFIG(2)
- `setting_5wifi_1.js`: WIFI_INIT_STATUS(417), WIRELESS5G_CONFIG(211)
- `setting_5wifi_2.js`: WIFI_INIT_STATUS(417), WIRELESS5G_CONFIG(211)
- `setting_5wifi_3.js`: WIFI_INIT_STATUS(417), WIRELESS5G_CONFIG(211)
- `setting_5wifi_4.js`: WIFI_INIT_STATUS(417), WIRELESS5G_CONFIG(211)
- `setting_apn.js`: APN_CONFIG(213), APN_INFO_PROCESS(248), MAIN_APN_MOVE_MULTI_APN(437), MULTI_APN_INFO(130)
- `setting_apn1.js`: APN_INFO_PROCESS(248), MULTI_APN_INFO(130)
- `setting_apn2.js`: APN_CONFIG(213)
- `trafficLimit_settings.js`: TRAFFIC_LIMIT_SETTING(337)
- `vlanSetting.js`: MUTIL_VLAN_CONFIG(290)
- `wanLinkDetectSetting.js`: WAN_LINK_DETECT_SETTING(336)
- `wifiList24g.js`: WIFI_INIT_STATUS(417), WIRELESS_MACFILTER(278)
- `wifiList5g.js`: WIFI_INIT_STATUS(417), WIRELESS_MACFILTER(278)
- `wifiPower.js`: WIFI_INIT_STATUS(417), WIRELESS_POWER(411)
- `wireless5gWpsSetting.js`: OPEN_RANDOM_PIN(244), SET_WPS_SUCCESS_FLAG(325), WIFI_INIT_STATUS(417), WIRELESS5G_CONFIG(211), WPS_CONFIG(132), WPS_PIN_CODE(243)
- `wirelessWpsSetting.js`: OPEN_RANDOM_PIN(244), SET_WPS_SUCCESS_FLAG(325), WIFI_INIT_STATUS(417), WIRELESS_CONFIG(2), WPS_CONFIG(132), WPS_PIN_CODE(243)
- `wlan24gAdvance.js`: WIFI_INIT_STATUS(417), WIRELESS_ADVANCE(230)
- `wlan5gAdvance.js`: WIFI_INIT_STATUS(417), WIRELESS5G_ADVANCE(231)
- `wlan5gTpc.js`: WIFI_INIT_STATUS(417), WLAN_5G_TPC(242)

## dashboard

- `dashboard.js`: AUTO_DIAL(222), GET_DASHBOARD_INDEX(401), NETWORKSET_MODE(218), WIFI_INIT_STATUS(417), WIRELESS5G_CONFIG(211), WIRELESS_CONFIG(2)

## firewall

- `accessControl.js`: FW_ACCESS_CONTROL_SIMPLE(345)
- `aclFilter.js`: FIRWALL_ACL_FILTER(31)
- `ddos.js`: DDOS_PROTECTION(275)
- `default.js`: DEFAULT_FILTER(28), IP_PORT_FILTER(32), MAC_DEFAULT_FILTER(30), MAC_FILTER(23), PORT_FILTER(21)
- `default2.js`: URL_DEFAULT_FILTER(29), URL_FILTER(26)
- `defaultMac.js`: MAC_DEFAULT_FILTER(30)
- `dmz.js`: NETWORK_SERVICE(172)
- `fw_switch_setting.js`: FW_SWITCH_SETTING(367)
- `gameTrafficAcceleration.js`: GAME_TRAFFIC_ACCELERATION(506)
- `ipFilter.js`: DEFAULT_FILTER(28), IP_PORT_FILTER(32)
- `ipMacBinding.js`: IP_MAC_BINDING(24)
- `macFilter.js`: DEFAULT_FILTER(28), MAC_FILTER(23)
- `portFilter.js`: DEFAULT_FILTER(28), PORT_FILTER(21)
- `portForward.js`: GET_SYSTEM_PORT(400), OTHER_FILTER(27)
- `remoteWebPortSetting.js`: REMOTE_WEBPORT_SETTING(334)
- `speedLimit.js`: SPEED_LIMIT(25)
- `staticArpBinding.js`: ARP_BINDING(83)
- `upnp.js`: FW_UPNP_STATUS(333)
- `urlFilter.js`: URL_DEFAULT_FILTER(29), URL_FILTER(26)

## industry

- `didoSetting.js`: DIDO_SETTING(353)
- `mqttSetting.js`: MQTT_SETTING(403)
- `serialApplication.js`: INDUSTRY_NETWORK_SET(379), MODBUS_SLAVE_MODULE_SET(381), MODBUS_SLAVE_SET(380)
- `serialDebug.js`: MODBUS_SLAVE_SERIAL_DATA_DEBUG(387)
- `serialSetting.js`: SERIAL_DATA_OPER(404), SERIAL_SETTING(388)
- `trafficStat.js`: TRAFFIC_DAY_STAT(407), TRAFFIC_HOUR_STAT(408), TRAFFIC_INTERFACE_LIST(406), TRAFFIC_SETTING(405)

## info

- `calibrationInfo.js`: GET_ENDC_INFO(273), GET_MOUNT_INFO(274), LTE_CALIBRATION(266), NR_CALIBRATION(267), WCDMA_CALIBRATION(421)
- `deviceInfo.js`: DEVICE_INFO(207)
- `dhcpConnected.js`: DHCPCLIENT_INFO(223)
- `lan_info.js`: LAN_INFO(208)
- `lan_info1.js`: LAN_INFO(208)
- `lan_info2.js`: LAN_INFO(208)
- `multi_wired_wan_info.js`: MULTI_WIRED_WAN_INFO(497)
- `neighborInfo.js`: GET_NEIGHBOR_INFO(282)
- `sysInfo.js`: SYS_INFO_NETWORK(205)
- `wan1_info.js`: MULTI_WAN_INFO(291)
- `wan_info.js`: ROUTER_INFO(133)
- `wifi24g1_info.js`: WIRELESS_CONFIG(2)
- `wifi24g2_info.js`: WIRELESS_CONFIG(2)
- `wifi24g3_info.js`: WIRELESS_CONFIG(2)
- `wifi24g4_info.js`: WIRELESS_CONFIG(2)
- `wifi24g_info.js`: WIRELESS_CONFIG(2)
- `wifi5g1_info.js`: WIRELESS5G_CONFIG(211)
- `wifi5g2_info.js`: WIRELESS5G_CONFIG(211)
- `wifi5g3_info.js`: WIRELESS5G_CONFIG(211)
- `wifi5g4_info.js`: WIRELESS5G_CONFIG(211)
- `wifi5g_info.js`: WIRELESS5G_CONFIG(211)
- `wired_wan.js`: ROUTER_INFO(133)
- `wireless5gConnected.js`: WIFI5G_LIST_INFO(225)
- `wirelessConnected.js`: WIFI24G_LIST_INFO(224)
- `wlan_wan.js`: ROUTER_INFO(133), WAN_WLAN_MODE(285)

## manage

- `deviceSelfCheck.js`: DEVICE_SELF_CHECK(484)
- `exportLog.js`: EXPORT_LOG(241)
- `logInfo.js`: LOG_INFO(322)
- `meshAdvSetting.js`: DHCPCLIENT_INFO(223), NETWORK_TOPOLOPY(315)
- `meshSetting.js`: MESH_SETTING(314)
- `meshSettingIndex.js`: MESH_SETTING(314)
- `sysAt.js`: SEND_AT(270)
- `sysLog.js`: EXPORT_HWSECURITY_LOG(366), SYS_LOG(17)
- `ussd.js`: SMS_SEND(13), SMS_SETTING(16), USSD_SEND(350)

## parent

- `parentControl.js`: PARENT_MODEL(391)
- `parentSpeed.js`: DHCPCLIENT_INFO(223), GETGLOBESTATUS(1003), PARENTAL_CONTROL_SPEED(382)
- `parentTime.js`: DHCPCLIENT_INFO(223), GETGLOBESTATUS(1003), PARENTAL_CONTROL_TIME(385)
- `parentUrl.js`: DHCPCLIENT_INFO(223), GETGLOBESTATUS(1003), PARENTAL_CONTROL_URL(383)

## phoneBook

- `phoneBook.js`: DEL_PHONE_BOOK(362), GET_PHONE_BOOK(361), SET_PHONE_BOOK(360)

## sms

- `smsInbox.js`: SMS_DELETE(14), SMS_INFO(12), SMS_SEND(13), SMS_SETTING(16)
- `smsOutbox.js`: SMS_DELETE(14), SMS_INFO(12), SMS_SEND(13), SMS_SETTING(16)
- `smsSetting.js`: SMS_SETTING(16)

## sys

- `adbSwitch.js`: ADB_SWITCH(237)
- `antennaChange.js`: CHANGE_ANTENNA_STATUS(363)
- `changePasswd.js`: CHANGE_PASSWD(102), LOGOUT(101)
- `changeUsername.js`: CHANGE_USERNAME(98)
- `commlog.js`: COMMLOG_BACKUP_TIME(262)
- `dstSettings.js`: DST_SETTING(351)
- `exportOrLoadConfig.js`: CONFIG_EXPORT(180), CONFIG_LOADER(199), SYS_UPDATE(5)
- `lightsOut.js`: LIGHTS_OUT_SETTING(378)
- `modemlogSwitch.js`: MODEM_LOG_SWITCH(236)
- `remoteConfigUpdate.js`: ONLINE_UPGRADE_AUTO(196)
- `restoreFactory.js`: RESTORE_DEFAULT(112)
- `service.js`: SYS_SERVICE_SET(234)
- `sfpIPA.js`: SFP_IPA_SETTING(255)
- `ssh.js`: SYS_SSH_SET(409)
- `sysUnormalRebootSwitch.js`: UNORMAL_REBOOT_SWITCH(328)
- `timeSetting.js`: SET_DATETIME(11), SYNC_CLIENT_TIME(321)
- `timeToRestart.js`: SET_DATETIME(11), TIME_TO_RESTART(263)
- `tr069Log.js`: TR069_LOG_SWITCH(268)
- `wifiToRestart.js`: WIFI_SCHEDULE_SETTING(503)

## tools

- `ping.js`: NETWORK_TOOLS(168)
- `restoreFactory.js`: REMOTE_PACKET_CAPTURE(245)
- `tcpdump.js`: NETWORK_TOOLS(168)
- `tracepath.js`: NETWORK_TOOLS(168)

## update

- `configUpdate.js`: CONFIG_UPDATE(184), RESTORE_DEFAULT(112), SYS_UPDATE(5)
- `fota.js`: FOTA_SETTINGS_NEW(480)
- `sysAutoUpdate.js`: DETECTION_VERSION_INFO(238), SYS_AUTO_UPGRADE(240), UPGRADE_IMMEDIATELY(239)
- `sysUpdate.js`: SYS_UPDATE(5), UPDATE_PARTIAL(106)

## voice

- `vioceBasicConfig.js`: VOICE_BASIC_CONFIG(295)
- `voiceAdvanceConfig.js`: VOICE_ADVANCE_CONFIG(294)
- `voipAdvancedSettings.js`: VOIP_ADVANCED_CONFIG(297)
- `voipCall.js`: VOIP_CALL_CIPHER(298)

## vpn

- `ipSec.js`: IPSEC_CONFIG(281), VPN_ONLY_ONE(425)
- `ipSecStatus.js`: IPSEC_CONFIG(281)
