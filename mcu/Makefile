TI_REQUIRED_TOOLS := MCU_PLUS_SDK_PATH SYSCFG_PATH CGT_TI_C7000_PATH CGT_TI_ARM_CLANG_PATH

all: check-tools
	@$(foreach ti_project_dir,$(MCU_TARGETS), \
		$(MAKE) -C "$(ti_project_dir)" -f makefile all;)

libs: check-tools
	$(MAKE) -C "$(MCU_PLUS_SDK_PATH)" -f makefile libs

clean: check-tools
	@$(foreach ti_project_dir,$(MCU_TARGETS), \
		$(MAKE) -C "$(ti_project_dir)" -f makefile clean;)

sysconfig: check-tools
	$(MAKE) -C "$(SYSCONFIG_TARGET)" -f makefile syscfg-gui;

check-tools:
	@$(foreach tool,$(TI_REQUIRED_TOOLS), \
		if [ ! -d "$($(tool))" ] || [ -z "$$(ls -A "$($(tool))")" ]; then \
			echo "$(COLOR_ERR)TI SDK is not available, please run 'task fetch-ti' to install$(COLOR_RESET)"; \
			exit 1; \
		fi;)

.PHONY: all libs clean sysconfig check-tools
