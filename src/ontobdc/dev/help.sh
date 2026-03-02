#!/bin/bash

ontobdc_help_dev() {
  echo ""
  echo -e "  ${WHITE}DEV MODULE COMMANDS${RESET}"
  echo ""
  echo -e "    ${CYAN}branch <create|checkout|changelog> [branch_name]${RESET}"
  echo -e "      ${GRAY}Manages branches across stack, test, web and root repos.${RESET}"
  echo ""
  echo -e "    ${CYAN}commit <message>${RESET}"
  echo -e "      ${GRAY}Commits and pushes changes across stack, test, web and root.${RESET}"
  echo ""
}

