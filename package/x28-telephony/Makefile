include $(TOPDIR)/rules.mk

PKG_NAME:=x28-telephony
PKG_VERSION:=0.1.0
PKG_RELEASE:=1
PKG_LICENSE:=GPL-2.0-only

include $(INCLUDE_DIR)/package.mk

define Package/x28-telephony
  SECTION:=net
  CATEGORY:=Network
  SUBMENU:=WWAN
  TITLE:=X28 text messages, phone book and an HTTP API with API keys
  DEPENDS:=+x28-mipc +lua +luci-base +luci-lib-jsonc +curl +flock
  PKGARCH:=all
endef

define Package/x28-telephony/description
  Text messages through the X28 modem's AT channel: a LuCI page (Services > Telephony) with the messages, a phone
  book and API keys, and an HTTP API for other machines on the LAN. Received messages are moved from the SIM to
  /etc/x28-telephony. Calls are not part of this package yet.
endef

define Build/Compile
endef

define Package/x28-telephony/install
	$(INSTALL_DIR) $(1)/usr/sbin $(1)/www/cgi-bin $(1)/etc/init.d $(1)/lib/upgrade/keep.d
	$(INSTALL_BIN) ./files/x28-sms $(1)/usr/sbin/x28-sms
	$(INSTALL_BIN) ./files/x28-telephony.cgi $(1)/www/cgi-bin/x28-telephony
	$(INSTALL_BIN) ./files/x28-telephony.init $(1)/etc/init.d/x28-telephony
	$(INSTALL_DATA) ./files/x28-telephony.keep $(1)/lib/upgrade/keep.d/x28-telephony
	$(CP) ./root/* $(1)/
	$(INSTALL_DIR) $(1)/www
	$(CP) ./htdocs/* $(1)/www/
endef

$(eval $(call BuildPackage,x28-telephony))
