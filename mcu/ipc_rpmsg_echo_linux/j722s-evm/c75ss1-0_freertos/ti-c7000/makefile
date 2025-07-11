#
# Auto generated makefile
#

export MCU_PLUS_SDK_PATH?=$(abspath ../../../../../../..)
include $(MCU_PLUS_SDK_PATH)/imports.mak
include $(MCU_PLUS_SDK_PATH)/devconfig/devconfig.mak

CG_TOOL_ROOT=$(CGT_TI_C7000_PATH)

CC=$(CG_TOOL_ROOT)/bin/cl7x
LNK=$(CG_TOOL_ROOT)/bin/cl7x
STRIP=$(CG_TOOL_ROOT)/bin/strip7x
OBJCOPY=$(CG_TOOL_ROOT)/bin/
ifeq ($(OS), Windows_NT)
	PYTHON=python
else
	PYTHON=python3
endif

PROFILE?=release
ConfigName:=$(PROFILE)

OUTNAME:=ipc_rpmsg_echo_linux.$(PROFILE).out

BOOTIMAGE_PATH=$(abspath .)
BOOTIMAGE_NAME:=ipc_rpmsg_echo_linux.$(PROFILE).appimage
BOOTIMAGE_NAME_XIP:=ipc_rpmsg_echo_linux.$(PROFILE).appimage_xip
BOOTIMAGE_NAME_SIGNED:=ipc_rpmsg_echo_linux.$(PROFILE).appimage.signed
BOOTIMAGE_RPRC_NAME:=ipc_rpmsg_echo_linux.$(PROFILE).rprc
BOOTIMAGE_RPRC_NAME_XIP:=ipc_rpmsg_echo_linux.$(PROFILE).rprc_xip
BOOTIMAGE_RPRC_NAME_TMP:=ipc_rpmsg_echo_linux.$(PROFILE).rprc_tmp
BOOTIMAGE_NAME_HS:=ipc_rpmsg_echo_linux.$(PROFILE).appimage.hs
BOOTIMAGE_NAME_HS_FS:=ipc_rpmsg_echo_linux.$(PROFILE).appimage.hs_fs
TARGETS := $(BOOTIMAGE_NAME)
ifeq ($(DEVICE_TYPE), HS)
   TARGETS += $(BOOTIMAGE_NAME_HS)
endif
SCISERVER_IMAGE_PATH:=$(MCU_PLUS_SDK_PATH)/tools/sysfw/sciserver_binary/j722s
SCISERVER_BOOTIMAGE_RPRC_NAME:=$(SCISERVER_IMAGE_PATH)/sciclient_get_version.release.rprc

FILES_common := \
	ipc_rpmsg_echo_linux.c \
	main.c \
	ti_drivers_config.c \
	ti_drivers_open_close.c \
	ti_board_config.c \
	ti_board_open_close.c \
	ti_dpl_config.c \
	ti_pinmux_config.c \
	ti_power_clock_config.c \

FILES_PATH_common = \
	.. \
	../../.. \
	generated \

INCLUDES_common := \
	-I${CG_TOOL_ROOT}/include \
	-I${MCU_PLUS_SDK_PATH}/source \
	-I${MCU_PLUS_SDK_PATH}/source/kernel/freertos/FreeRTOS-Kernel/include \
	-I${MCU_PLUS_SDK_PATH}/source/kernel/freertos/portable/TI_CGT/DSP_C75X \
	-I${MCU_PLUS_SDK_PATH}/source/kernel/freertos/config/j722s/c75x \
	-I${MCU_PLUS_SDK_PATH}/examples/drivers/ipc/ipc_rpmsg_echo_linux \
	-Igenerated \

DEFINES_common := \
	-DSOC_J722S \

CFLAGS_common := \
	-DBUILD_C75X_2 \
	-mv7524 \
	--abi=eabi \
	-q \
	-mo \
	-pden \
	-pds=238 \
	-pds=880 \
	-pds1110 \
	--endian=little \
	--disable_inlining \
	-ea.se71 \
	--emit_warnings_as_errors \
	--diag_suppress=770 \
	--diag_suppress=69 \
	--diag_suppress=70 \
	--advice:performance=none \

CFLAGS_debug := \
	-Dxdc_target_name__=C71 \
	-D_DEBUG_=1 \
	--opt_level=0 \
	--symdebug:dwarf \
	-DBUILD_C75X \

CFLAGS_release := \
	-Dxdc_target_name__=C71 \
	--opt_level=3 \
	-DBUILD_C75X \

LNK_FILES_common = \
	linker.cmd \

LIBS_PATH_common = \
	-i${MCU_PLUS_SDK_PATH}/source/kernel/freertos/lib \
	-i${MCU_PLUS_SDK_PATH}/source/drivers/lib \
	-i${MCU_PLUS_SDK_PATH}/source/board/lib \
	-i${CG_TOOL_ROOT}/lib \

LIBS_common = \
	-lfreertos.j722s.c75x.ti-c7000.${ConfigName}.lib \
	-ldrivers.j722s.c75ss1-0.ti-c7000.${ConfigName}.lib \
	-llibc.a \

LFLAGS_common = \
	--silicon_version=7524 \
	-z \
	--emit_warnings_as_errors \
	--diag_suppress=10063 \
	--ram_model \
	--warn_sections \
	-q \
	-x \
	 \


LIBS_NAME = \
	freertos.j722s.c75x.ti-c7000.${ConfigName}.lib \
	drivers.j722s.c75ss1-0.ti-c7000.${ConfigName}.lib \
	libc.a \

LIBS_PATH_NAME = \
	${MCU_PLUS_SDK_PATH}/source/kernel/freertos/lib \
	${MCU_PLUS_SDK_PATH}/source/drivers/lib \
	${MCU_PLUS_SDK_PATH}/source/board/lib \
	${CG_TOOL_ROOT}/lib \

FILES := $(FILES_common) $(FILES_$(PROFILE))
ASMFILES := $(ASMFILES_common) $(ASMFILES_$(PROFILE))
FILES_PATH := $(FILES_PATH_common) $(FILES_PATH_$(PROFILE))
CFLAGS := $(CFLAGS_common) $(CFLAGS_$(PROFILE))
DEFINES := $(DEFINES_common) $(DEFINES_$(PROFILE))
INCLUDES := $(INCLUDES_common) $(INCLUDE_$(PROFILE))
LIBS := $(LIBS_common) $(LIBS_$(PROFILE))
LIBS_PATH := $(LIBS_PATH_common) $(LIBS_PATH_$(PROFILE))
LFLAGS := $(LFLAGS_common) $(LFLAGS_$(PROFILE))
LNK_FILES := $(LNK_FILES_common) $(LNK_FILES_$(PROFILE))

OBJDIR := obj/$(PROFILE)/
OBJS := $(FILES:%.c=%.obj)
OBJS += $(ASMFILES:%.S=%.obj)
DEPS := $(FILES:%.c=%.d)

vpath %.obj $(OBJDIR)
vpath %.c $(FILES_PATH)
vpath %.S $(FILES_PATH)
vpath %.lib $(LIBS_PATH_NAME)
vpath %.a $(LIBS_PATH_NAME)

$(OBJDIR)/%.obj %.obj: %.c
	@echo  Compiling: j722s:c75ss1-0:freertos:ti-c7000 $(OUTNAME): $<
	$(CC) $(CFLAGS) $(INCLUDES) $(DEFINES) -ppd=$(OBJDIR)/$(basename $@).d -ppa -fr=$(OBJDIR)/ -fc=$<

$(OBJDIR)/%.obj %.obj: %.S
	@echo  Compiling: j722s:c75ss1-0:freertos:ti-c7000 $(LIBNAME): $<
	$(CC) $(CFLAGS) $(INCLUDES) $(DEFINES) -ppd=$(OBJDIR)/$(basename $@).d -ppa -fr=$(OBJDIR)/ -fa=$<

all: $(TARGETS)

SYSCFG_GEN_FILES=generated/ti_drivers_config.c generated/ti_drivers_config.h
SYSCFG_GEN_FILES+=generated/ti_drivers_open_close.c generated/ti_drivers_open_close.h
SYSCFG_GEN_FILES+=generated/ti_dpl_config.c generated/ti_dpl_config.h
SYSCFG_GEN_FILES+=generated/ti_pinmux_config.c generated/ti_power_clock_config.c
SYSCFG_GEN_FILES+=generated/ti_board_config.c generated/ti_board_config.h
SYSCFG_GEN_FILES+=generated/ti_board_open_close.c generated/ti_board_open_close.h

$(OUTNAME): syscfg $(SYSCFG_GEN_FILES) $(OBJS) $(LNK_FILES) $(LIBS_NAME)
	@echo  .
	@echo  Linking: j722s:c75ss1-0:freertos:ti-c7000 $@ ...
	$(LNK) $(LFLAGS) $(LIBS_PATH) -m=$(basename $@).map -o $@ $(addprefix $(OBJDIR), $(OBJS)) $(LIBS) $(LNK_FILES)
	$(RM) ipc_rpmsg_echo_linux.c75ss1-0.${ConfigName}.strip.out
	$(STRIP) -p $@ -o=ipc_rpmsg_echo_linux.c75ss1-0.${ConfigName}.strip.out
	@echo  Linking: j722s:c75ss1-0:freertos:ti-c7000 $@ Done !!!
	@echo  .

clean:
	@echo  Cleaning: j722s:c75ss1-0:freertos:ti-c7000 $(OUTNAME) ...
	$(RMDIR) $(OBJDIR)
	$(RM) $(OUTNAME)
	$(RM) ipc_rpmsg_echo_linux.c75ss1-0.${ConfigName}.strip.out
	$(RM) $(BOOTIMAGE_NAME)
	$(RM) $(BOOTIMAGE_NAME_XIP)
	$(RM) $(BOOTIMAGE_NAME_SIGNED)
	$(RM) $(BOOTIMAGE_NAME_HS)
	$(RM) $(BOOTIMAGE_NAME_HS_FS)
	$(RM) $(BOOTIMAGE_RPRC_NAME)
	$(RM) $(BOOTIMAGE_RPRC_NAME_XIP)
	$(RMDIR) generated/

scrub:
	@echo  Scrubing: j722s:c75ss1-0:freertos:ti-c7000 ipc_rpmsg_echo_linux ...
	$(RMDIR) obj
ifeq ($(OS),Windows_NT)
	$(RM) \*.out
	$(RM) \*.map
	$(RM) \*.appimage*
	$(RM) \*.rprc*
	$(RM) \*.tiimage*
	$(RM) \*.bin
else
	$(RM) *.out
	$(RM) *.map
	$(RM) *.appimage*
	$(RM) *.rprc*
	$(RM) *.tiimage*
	$(RM) *.bin
endif
	$(RMDIR) generated

$(OBJS): | $(OBJDIR)

$(OBJDIR):
	$(MKDIR) $@

.NOTPARALLEL:

.INTERMEDIATE: syscfg
$(SYSCFG_GEN_FILES): syscfg

syscfg: ../example.syscfg
	@echo Generating SysConfig files ...
	$(SYSCFG_NODE) $(SYSCFG_CLI_PATH)/dist/cli.js --product $(SYSCFG_SDKPRODUCT) --context c75ss1-0 --part Default --package AMW --output generated/ ../example.syscfg

syscfg-gui:
	$(SYSCFG_NWJS) $(SYSCFG_PATH) --product $(SYSCFG_SDKPRODUCT) --device J722S_TDA4VEN_TDA4AEN_AM67 --context c75ss1-0 --part Default --package AMW --output generated/  ../example.syscfg

#
# Generation of boot image which can be loaded by Secondary Boot Loader (SBL)
#
ifeq ($(OS),Windows_NT)
EXE_EXT=.exe
endif
ifeq ($(OS),Windows_NT)
  BOOTIMAGE_CERT_GEN_CMD=powershell -executionpolicy unrestricted -command $(MCU_PLUS_SDK_PATH)/tools/boot/signing/x509CertificateGen.ps1
else
  BOOTIMAGE_CERT_GEN_CMD=$(MCU_PLUS_SDK_PATH)/tools/boot/signing/x509CertificateGen.sh
endif
BOOTIMAGE_TEMP_OUT_FILE=temp_stdout_$(PROFILE).txt

BOOTIMAGE_CERT_KEY=$(APP_SIGNING_KEY)

BOOTIMAGE_CORE_ID_mcu-r5fss0-0  = 0
BOOTIMAGE_CORE_ID_wkup-r5fss0-0 = 1
BOOTIMAGE_CORE_ID_main-r5fss0-0 = 2
BOOTIMAGE_CORE_ID_c75ss0-0      = 3
BOOTIMAGE_CORE_ID_c75ss1-0      = 4
BOOTIMAGE_CORE_ID_a53ss0-0      = 5
BOOTIMAGE_CORE_ID_a53ss0-1      = 6
BOOTIMAGE_CORE_ID_a53ss1-0      = 7
BOOTIMAGE_CORE_ID_a53ss1-1      = 8
BOOTIMAGE_CORE_ID_hsm-m4fss0-0  = 9
SBL_RUN_ADDRESS=0x43C00000
SBL_DEV_ID=55

MULTI_CORE_IMAGE_GEN = $(SYSCFG_NODE) $(MCU_PLUS_SDK_PATH)/tools/boot/multicoreImageGen/multicoreImageGen.js
OUTRPRC_CMD = $(SYSCFG_NODE) $(MCU_PLUS_SDK_PATH)/tools/boot/out2rprc/elf2rprc.js
APP_IMAGE_SIGN_CMD = $(MCU_PLUS_SDK_PATH)/tools/boot/signing/appimage_x509_cert_gen.py

ifeq ($(OS),Windows_NT)
  XIPGEN_CMD=$(MCU_PLUS_SDK_PATH)/tools/boot/xipGen/xipGen.exe
else
  XIPGEN_CMD=$(MCU_PLUS_SDK_PATH)/tools/boot/xipGen/xipGen.out
endif

MULTI_CORE_IMAGE_PARAMS = \
	$(SCISERVER_BOOTIMAGE_RPRC_NAME)@$(BOOTIMAGE_CORE_ID_wkup-r5fss0-0) \
	$(BOOTIMAGE_RPRC_NAME)@$(BOOTIMAGE_CORE_ID_c75ss1-0) \

MULTI_CORE_IMAGE_PARAMS_XIP = \
	$(BOOTIMAGE_RPRC_NAME_XIP)@$(BOOTIMAGE_CORE_ID_c75ss1-0) \

$(BOOTIMAGE_NAME): $(OUTNAME)
	@echo  Boot image: j722s:c75ss1-0:freertos:ti-c7000 $(BOOTIMAGE_PATH)/$@ ...
ifneq ($(OS),Windows_NT)
	$(CHMOD) a+x $(XIPGEN_CMD)
endif
	$(OUTRPRC_CMD) $(OUTNAME) >> $(BOOTIMAGE_TEMP_OUT_FILE)
	$(COPY) $(BOOTIMAGE_RPRC_NAME) $(BOOTIMAGE_RPRC_NAME_TMP)
	$(RM) $(BOOTIMAGE_RPRC_NAME)
	$(XIPGEN_CMD) -i $(BOOTIMAGE_RPRC_NAME_TMP) -o $(BOOTIMAGE_RPRC_NAME) -x $(BOOTIMAGE_RPRC_NAME_XIP) --flash-start-addr 0x60000000 -v > $(BOOTIMAGE_TEMP_OUT_FILE)
	$(MULTI_CORE_IMAGE_GEN) --devID $(SBL_DEV_ID) --out $(BOOTIMAGE_NAME) $(MULTI_CORE_IMAGE_PARAMS) >> $(BOOTIMAGE_TEMP_OUT_FILE)
	$(MULTI_CORE_IMAGE_GEN) --devID $(SBL_DEV_ID) --out $(BOOTIMAGE_NAME_XIP) $(MULTI_CORE_IMAGE_PARAMS_XIP) >> $(BOOTIMAGE_TEMP_OUT_FILE)
# Sign the appimage for HS-FS using appimage signing script
	$(PYTHON) $(APP_IMAGE_SIGN_CMD) --bin $(BOOTIMAGE_NAME) --authtype 2 --key $(APP_SIGNING_KEY) --output $(BOOTIMAGE_NAME_HS_FS)
	$(RM) $(BOOTIMAGE_RPRC_NAME_TMP)
	$(RM) $(BOOTIMAGE_TEMP_OUT_FILE)
	@echo  Boot image: j722s:c75ss1-0:freertos:ti-c7000 $(BOOTIMAGE_PATH)/$@ Done !!!
	@echo  .
	@echo  Boot image: j722s:c75ss1-0:freertos:ti-c7000 $(BOOTIMAGE_PATH)/$(BOOTIMAGE_NAME_HS_FS) Done !!!
	@echo  .

$(BOOTIMAGE_NAME_HS): $(BOOTIMAGE_NAME)
ifeq ($(DEVICE_TYPE), HS)
# Sign the appimage using appimage signing script
ifeq ($(ENC_ENABLED),no)
	@echo Boot image signing: Encryption is disabled.
	$(PYTHON) $(APP_IMAGE_SIGN_CMD) --bin $(BOOTIMAGE_NAME) --authtype 2 --key $(APP_SIGNING_KEY) --output $(BOOTIMAGE_NAME_HS)
else
	@echo Boot image signing: Encryption is enabled.
	$(PYTHON) $(APP_IMAGE_SIGN_CMD) --bin $(BOOTIMAGE_NAME) --authtype 2 --key $(APP_SIGNING_KEY) --enc y --enckey $(APP_ENCRYPTION_KEY) --output $(BOOTIMAGE_NAME_HS)
	$(RM) $(BOOTIMAGE_NAME)-enc
endif
	@echo  Boot image: j722s:c75ss1-0:freertos:ti-c7000 $(BOOTIMAGE_PATH)/$(BOOTIMAGE_NAME_HS) Done !!!
	@echo  .
endif
-include $(addprefix $(OBJDIR)/, $(DEPS))
