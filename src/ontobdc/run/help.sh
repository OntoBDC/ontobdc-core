#!/bin/bash

ontobdc_help_run() {
  echo ""
  echo -e "  ${WHITE}RUN MODULE COMMANDS${RESET}"
  echo ""
  echo -e "    ${CYAN}run <capability_id> [args...]${RESET}"
  echo -e "      ${GRAY}Executes a registered capability using the ontobdc runner.${RESET}"
  echo ""
  echo -e "    ${CYAN}run --json${RESET}"
  echo -e "      ${GRAY}Prints the capability catalog in JSON format.${RESET}"
  echo ""
  echo -e "    ${CYAN}plan <capability_id> [--context key=value ...]${RESET}"
  echo -e "      ${GRAY}Builds and displays an execution plan for a capability.${RESET}"
  echo ""
}

