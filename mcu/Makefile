TI_REQUIRED_TOOLS := MCU_PLUS_SDK_PATH SYSCFG_PATH CGT_TI_C7000_PATH CGT_TI_ARM_CLANG_PATH

all: check-tools
	@$(foreach ti_project_dir,$(MCU_TARGETS), \
		$(MAKE) -C "$(ti_project_dir)" -f makefile all;)

clean: check-tools
	@$(foreach ti_project_dir,$(MCU_TARGETS), \
		$(MAKE) -C "$(ti_project_dir)" -f makefile clean;)

sysconfig: check-tools
	$(MAKE) -C "$(SYSCONFIG_TARGET)" -f makefile syscfg-gui;

check-tools:
	@$(foreach tool,$(TI_REQUIRED_TOOLS), \
		if [ ! -d "$($(tool))" ] || [ -z "$(shell ls -A "$($(tool))")" ]; then \
			echo "ERROR: $($(tool)) directory does not exist or it is empty"; \
			exit 1; \
		fi;)

.PHONY: all clean run-ti check-tools
