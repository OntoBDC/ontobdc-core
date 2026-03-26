#!/bin/bash

ontobdc_help_dev() {
  local CONTENT=""
  CONTENT="${CONTENT}  \033[37mUsage:\033[0m\n"
  CONTENT="${CONTENT}    \033[90montobdc dev <command> [args]\033[0m\n\n"
  CONTENT="${CONTENT}  \033[37mCommands:\033[0m\n"
  CONTENT="${CONTENT}    \033[36m--help\033[0m                               \033[90mShow this help\033[0m\n"
  CONTENT="${CONTENT}    \033[36m--enable-dev-tool\033[0m                    \033[90mEnable dev.tool in .__ontobdc__/config.yaml (must be passed alone)\033[0m\n"
  CONTENT="${CONTENT}    \033[36mcommit <message>\033[0m                     \033[90mCommit and push changes across repos\033[0m\n"
  CONTENT="${CONTENT}    \033[36m<branch-create|checkout|changelog>\033[0m   \033[90mBranch workflow across repos\033[0m\n"
  CONTENT="${CONTENT}    \033[36mrepo --add-ssh-key <path>\033[0m            \033[90mPersist SSH key path into .__ontobdc__/config.yaml (dev.repo.ssh.key_path)\033[0m\n"
  CONTENT="${CONTENT}    \033[36mrepo --rm-ssh-key <path>\033[0m             \033[90mRemove SSH key path from .__ontobdc__/config.yaml\033[0m\n\n"
  CONTENT="${CONTENT}  \033[37mNotes:\033[0m\n"
  CONTENT="${CONTENT}    \033[90mMost dev commands require \033[1;37mdev.tool: enable\033[0;90m in .__ontobdc__/config.yaml.\033[0m\n"
  CONTENT="${CONTENT}    \033[90mRun: \033[1;37montobdc dev --enable-dev-tool\033[0;90m\033[0m\n"

  if type print_message_box &>/dev/null; then
    print_message_box "GRAY" "OntoBDC" "Dev Help" "$CONTENT"
  else
    echo -e "$CONTENT"
  fi
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  ontobdc_help_dev
fi
