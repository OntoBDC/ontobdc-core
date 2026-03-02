
import re
import os
import hashlib
import mimetypes
from datetime import datetime
from typing import Any, Dict, List, Optional
from ontobdc.module.resource.adapter.archive import ZipArchiveAdapter
from ontobdc.module.resource.domain.port.repository import FileRepositoryPort
from ontobdc.module.resource.audit.repository import HasReadPermission, HasWritePermission
from ontobdc.run.core.action import Action, ActionMetadata
from ontobdc.run.core.capability import CapabilityExecutor, CapabilityRegistry
from ontobdc.module.social.audit.account import ValidWhatsappAccount
from ontobdc.module.resource.adapter.datapackage import DataPackageAdapter
from ontobdc.module.social.adapter.strategy.cli_whatsapp import ExtractWhatsappCliStrategy


class ExtractUnansweredWhatsappMessages(Action):
    """
    Extracts unanswered WhatsApp messages from a zip document.
    """
    METADATA = ActionMetadata(
        id="org.ontobdc.domain.resource.action.extract_unanswered_whatsapp_messages",
        version="0.1.0",
        name="Extract Unanswered WhatsApp Messages",
        description="Extracts unanswered WhatsApp messages from a zip document.",
        author=["Elias M. P. Junior"],
        tags=["social", "whatsapp", "extraction", "analysis", "report"],
        supported_languages=["en", "pt_BR"],
        input_schema={
            "type": "object",
            "properties": {
                "whatsapp-account": {
                    "type": "urn",
                    "required": True,
                    "description": "The name of the WhatsApp account (to identify sent messages vs received).",
                    "check": [ValidWhatsappAccount()],
                },
                "repository": {
                    "type": FileRepositoryPort,
                    "required": True,
                    "description": "Repository instance containing the WhatsApp exports",
                    "check": [HasReadPermission, HasWritePermission],
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "org.ontobdc.domain.social.interaction.list.content": {
                    "type": "array",
                    "description": "List of unanswered interactions",
                },
                "org.ontobdc.domain.social.interaction.list.count": {
                    "type": "integer",
                    "description": "Number of interactions listed",
                },
            },
        },
    )

    def get_default_cli_strategy(self, **kwargs: Any) -> Any:
        return ExtractWhatsappCliStrategy(**kwargs)

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        account_name = inputs.get("whatsapp-account")
        repository = inputs.get("repository")

        # Filter by type 'zip'
        list_by_type_cls = CapabilityRegistry.get("org.ontobdc.domain.resource.capability.list_documents_by_type")
        if not list_by_type_cls:
             raise ValueError("Capability not found: org.ontobdc.domain.resource.capability.list_documents_by_type")
        
        type_output = CapabilityExecutor().execute(
            capability=list_by_type_cls(),
            inputs={
                "repository": repository,
                "file-type": ["zip"]
            }
        )
        files_by_type = set(type_output.get("org.ontobdc.domain.resource.document.list.content", []))

        # Filter by name pattern 'WhatsApp Chat with*'
        list_by_name_cls = CapabilityRegistry.get("org.ontobdc.domain.resource.capability.list_documents_by_name_pattern")
        if not list_by_name_cls:
             raise ValueError("Capability not found: org.ontobdc.domain.resource.capability.list_documents_by_name_pattern")

        name_output = CapabilityExecutor().execute(
            capability=list_by_name_cls(),
            inputs={
                "repository": repository,
                "file-name": "WhatsApp Chat with*"
            }
        )
        files_by_name = set(name_output.get("org.ontobdc.domain.resource.document.list.content", []))

        # Intersect results
        target_files = list(files_by_type.intersection(files_by_name))

        validator: ValidWhatsappAccount = self.METADATA.input_schema["properties"]["whatsapp-account"]["check"][0]
        whatsapp_account: Dict[str, Any] = validator.get_account(account_name, inputs)

        from rich.progress import Progress, SpinnerColumn, TextColumn

        unpacked_folders = []
        unanswered = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True
        ) as progress:
            
            # 1. Extraction Phase
            task_extract = progress.add_task(f"[cyan]Extracting {len(target_files)} chats...", total=len(target_files))
            
            for file_path in target_files:
                adapter = ZipArchiveAdapter(repository, file_path)
                adapter.extract()
                
                # Construct folder path where zip was extracted
                # ZipArchiveAdapter extracts to: dirname(zip_path)/basename_no_ext
                import os
                zip_filename = os.path.basename(file_path)
                folder_name = os.path.splitext(zip_filename)[0]
                target_dir = os.path.join(os.path.dirname(file_path), folder_name)
                
                unpacked_folders.append(target_dir)
                progress.advance(task_extract)

            # 2. Processing Phase
            task_process = progress.add_task(f"[green]Processing {len(unpacked_folders)} conversations...", total=len(unpacked_folders))
            
            for folder_path in unpacked_folders:
                messages = self._extract_messages(folder_path, repository, whatsapp_account)
                last_msg = self._get_last_message(messages)
                
                if last_msg and self._is_message_unanswered(last_msg, whatsapp_account):
                    unanswered.append(folder_path)
                
                progress.advance(task_process)
        
        return {
            "org.ontobdc.domain.social.interaction.list.content": unanswered,
            "org.ontobdc.domain.social.interaction.list.count": len(unanswered),
        }

    def _process_new_messages(self, current_round: int, dp_adapter: DataPackageAdapter, repository: FileRepositoryPort, target_file_path: str, whatsapp_account: Dict[str, Any]):
        # 3. Read and process new messages
        new_extracted_messages = self._read_messages(target_file_path, repository)

        new_processed_messages = []
        
        # Build set of existing hashes for fast lookup
        existing_messages = dp_adapter.read_csv_resource("messages")
        existing_hashes = set(m.get("hash") for m in existing_messages if m.get("hash"))
        
        file_content_hash = hashlib.md5()
        
        # Re-read file content for hashing the whole file (to rename later)
        with repository.open_file(target_file_path, "r") as f:
            raw_content = f.read()
            file_content_hash.update(raw_content.encode('utf-8'))
        
        file_hash = file_content_hash.hexdigest()

        for msg in new_extracted_messages:
            # Parse metadata
            dt = self._parse_timestamp(msg)
            author = self._get_message_author(msg)
            content = msg.get("content", "")
            
            # Generate hash
            hash_input = f"{dt.isoformat()}|{author}|{content}"
            msg_hash = hashlib.md5(hash_input.encode('utf-8')).hexdigest()
            
            if msg_hash in existing_hashes:
                continue # Skip duplicate
            
            new_processed_messages.append({
                "round": current_round,
                "data": dt.strftime("%Y-%m-%d") if dt != datetime.min else "",
                "hora": dt.strftime("%H:%M:%S") if dt != datetime.min else "",
                "mensagem": content,
                "author": author or "",
                "hash": msg_hash,
                "is_owner": not self._is_message_unanswered(msg, whatsapp_account) if author else False
            })
            
            existing_hashes.add(msg_hash)

        # 4. Save if there are new messages
        if new_processed_messages:
            all_messages = existing_messages + new_processed_messages
            
            dp_adapter.add_resource(
                resource_name="messages", 
                data=all_messages, 
                path="messages.csv"
            )
            dp_adapter.save()
            
            # Update return list
            existing_messages = all_messages

        # 5. Rename processed file
        # New name: original_{hash}.txt
        new_filename = f"original_{file_hash}.txt"
        new_file_path = f"{os.path.dirname(target_file_path)}/{new_filename}"
        
        # Rename
        repository.rename(target_file_path, new_file_path)

    def _extract_messages(self, folder_path: str, repository: FileRepositoryPort, whatsapp_account: Dict[str, Any]) -> List[Dict[str, Any]]:
        # 1. Setup paths
        folder_name: str = folder_path.rstrip('/').split('/')[-1]
        potential_paths = [
            f"{folder_path}/{folder_name}.txt",
            f"{folder_path}/_chat.txt"
        ]
        
        target_file_path = None
        for path in potential_paths:
            if repository.exists(path):
                target_file_path = path
                break
        
        # 2. Load existing messages from Data Package
        dp_adapter = DataPackageAdapter(repository, folder_path)
        existing_messages = dp_adapter.read_csv_resource("messages")

        if target_file_path:
            # Calculate next round
            current_round = 1
            if existing_messages:
                rounds = [int(m.get("round", 0)) for m in existing_messages if m.get("round")]
                if rounds:
                    current_round = max(rounds) + 1

            self._process_new_messages(
                current_round = current_round, 
                dp_adapter = dp_adapter, 
                repository = repository, 
                target_file_path = target_file_path, 
                whatsapp_account = whatsapp_account
            )

        self._process_attachments(
            dp_adapter = dp_adapter,
            folder_path = folder_path,
            current_round = current_round
        )

        self._process_statistics(
            dp_adapter = dp_adapter
        )

        self._process_unanswered_messages(
            dp_adapter = dp_adapter, 
            repository = repository, 
            folder_path = folder_path
        )

        return dp_adapter.read_csv_resource("messages")

    def _process_attachments(self, dp_adapter: DataPackageAdapter, folder_path: str, current_round: int):        
        # Load existing attachments
        existing_attachments = dp_adapter.read_csv_resource("attachments")
        existing_names = set(a.get("file_path") for a in existing_attachments if a.get("file_path"))
        
        # List files in folder
        # Assuming folder_path is accessible via os
        # Exclude known metadata files
        exclude_files = {"_chat.txt", "datapackage.json", ".DS_Store"}
        
        # Also exclude the folder itself if it appears in listing (unlikely with listdir)
        # And exclude .__ontobdc__ folder
        
        new_attachments = []
        
        # We need to walk or list. Since attachments are likely flat in the folder (from zip), listdir is enough.
        # But ZipArchiveAdapter extracts to a folder.
        
        try:
            # If path is absolute, use it. If relative, join with repo root?
            # folder_path usually comes from list_documents which might return relative.
            # But ZipArchiveAdapter returns absolute paths usually?
            # Let's try to resolve it via repository open_file logic or assume it is valid for os.
            # If repository is SimpleFileRepository, it handles local paths.
            
            # Use repository to list files? No method.
            # Try os.listdir if path exists locally
            
            files = []
            if os.path.exists(folder_path):
                files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
            
            for filename in files:
                if filename in exclude_files or filename.startswith("original_") or filename.startswith("."):
                    continue
                
                # Check if already processed (by name)
                if filename in existing_names:
                    continue
                
                file_full_path = os.path.join(folder_path, filename)
                
                # Get stats
                stat = os.stat(file_full_path)
                size = stat.st_size
                created_at = datetime.fromtimestamp(stat.st_ctime).isoformat()
                
                # Mimetype
                mime, _ = mimetypes.guess_type(filename)
                
                # Hash (optional per request: "hash (não repete attachment -> pelo nome, não hash)")
                # But user asked for hash field.
                # Let's calculate hash of content?
                # User said: "hash (não repete attachment -> pelo nome, não hash)"
                # This means: Deduplicate by name, BUT include hash field.
                
                # Calculate MD5
                file_hash = hashlib.md5()
                with open(file_full_path, "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        file_hash.update(chunk)
                
                new_attachments.append({
                    "round": current_round,
                    "file_path": filename,
                    "content_size": size,
                    "created_at": created_at,
                    "encoding_format": mime or "application/octet-stream",
                    "hash": file_hash.hexdigest()
                })
                
                existing_names.add(filename)
                
        except Exception as e:
            print(f"Error processing attachments: {e}")
            
        if new_attachments:
            all_attachments = existing_attachments + new_attachments
            dp_adapter.add_resource("attachments", all_attachments, path="attachments.csv")
            dp_adapter.save()

    def _process_statistics(self, dp_adapter: DataPackageAdapter):
        messages = dp_adapter.read_csv_resource("messages")
        if not messages:
            return

        # Calculate stats
        # author, qtd mensagens, max delay to answer, last_message_at
        
        authors_stats = {}
        
        # Sort messages by datetime just in case
        # messages are dicts with 'data' and 'hora' strings.
        # We need to parse them back to datetime objects for calculation.
        
        parsed_msgs = []
        for m in messages:
            dt_str = f"{m['data']} {m['hora']}"
            try:
                dt = datetime.strptime(dt_str.strip(), "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue # Skip invalid
            parsed_msgs.append({**m, "datetime": dt})
            
        parsed_msgs.sort(key=lambda x: x["datetime"])
        
        last_msg_time = None
        last_author = None
        
        for m in parsed_msgs:
            author = m.get("author") or "Unknown"
            dt = m["datetime"]
            is_msg_owner = str(m.get("is_owner", "False")).lower() == "true"
            
            if author not in authors_stats:
                authors_stats[author] = {
                    "author": author,
                    "is_owner": is_msg_owner,
                    "qtd_mensagens": 0,
                    "max_delay_seconds": 0,
                    "last_message_at": dt,
                    "last_message_content": ""
                }
            
            # Ensure is_owner is set if any message is owned
            if is_msg_owner:
                authors_stats[author]["is_owner"] = True
            
            stats = authors_stats[author]
            stats["qtd_mensagens"] += 1
            if dt >= stats["last_message_at"]:
                stats["last_message_at"] = dt
                stats["last_message_content"] = m.get("mensagem") or m.get("content") or ""
            
            # Delay calculation
            # Delay is time since LAST message from ANOTHER author?
            # Or time since last message in chat?
            # "max delay to answer" usually means how long THIS author took to reply to SOMEONE ELSE.
            if last_msg_time and last_author and last_author != author:
                delay = (dt - last_msg_time).total_seconds()
                if delay > stats["max_delay_seconds"]:
                    stats["max_delay_seconds"] = delay
            
            last_msg_time = dt
            last_author = author
            
        # Convert stats to structured list for JSON
        senders_list = []
        for author, data in authors_stats.items():
            senders_list.append({
                "name": data["author"],
                "is_owner": data["is_owner"],
                "message_count": data["qtd_mensagens"],
                "max_delay_seconds": data["max_delay_seconds"],
                "last_message": {
                    "at": data["last_message_at"].isoformat(),
                    "content": data["last_message_content"]
                }
            })
            
        # Build final JSON structure
        final_stats = {
            "senders": senders_list,
            "messages": messages
        }
            
        # Save (overwrite) as JSON
        dp_adapter.add_resource("statistics", final_stats, path="statistics.json")
        dp_adapter.save()

    def _process_unanswered_messages(self, dp_adapter: DataPackageAdapter, repository: FileRepositoryPort, folder_path: str):
        import json
        
        messages = dp_adapter.read_csv_resource("messages")
        if not messages:
            return

        # Check if last message is unanswered
        # We need to re-evaluate based on the full list logic
        # But we don't have whatsapp_account here easily unless passed.
        # However, messages.csv has 'is_owner' field!
        
        last_msg = messages[-1]
        is_owner = str(last_msg.get("is_owner", "False")).lower() == "true"
        
        # Unanswered means last message is NOT from owner
        if not is_owner:
            # Generate prompt
            # Load template
            # Hardcoded path relative to project root?
            # We can try to find it relative to this file or hardcoded.
            # Using the path from user snippet: ontobdc/prompt/whatsapp/analyze_chat.md
            
            # Assuming we run from project root or can resolve it.
            # Let's assume absolute path based on repository root or try relative.
            # The prompt file is in source code, not in the data repository.
            
            # Try to locate prompt file relative to this script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            # ontobdc/module/social/plugin/action/ -> ... -> ontobdc
            # We are deep.
            # Let's assume we can construct path from known root anchor
            
            # HACK: Assume CWD is project root or close enough, or find it.
            # Better: use the absolute path pattern if we know where code is installed.
            # But let's try a safe approach:
            # We know user said: ontobdc/prompt/whatsapp/analyze_chat.md
            
            prompt_path = os.path.join(os.getcwd(), "ontobdc/prompt/whatsapp/analyze_chat.md")
            if not os.path.exists(prompt_path):
                 # Try relative to this file
                 # ../../../../../prompt/whatsapp/analyze_chat.md
                 prompt_path = os.path.join(script_dir, "../../../../../prompt/whatsapp/analyze_chat.md")
            
            if os.path.exists(prompt_path):
                with open(prompt_path, "r", encoding="utf-8") as f:
                    template_content = f.read()
                
                # Get last N messages for context (e.g. 20)
                context_msgs = messages[-20:]
                messages_json_str = json.dumps(context_msgs, ensure_ascii=False, indent=2)
                
                final_prompt = template_content.replace("{{MESSAGES_JSON}}", messages_json_str)
                
                # Save to .__ontobdc__/analyze_chat.md
                # dp_adapter uses .__ontobdc__ relative to base_path.
                # We can use dp_adapter logic or write directly.
                # Let's use dp_adapter helper if we had one for arbitrary files, but we don't.
                # We can write using repository.open_file
                
                target_path = f"{folder_path}/.__ontobdc__/analyze_chat.md"
                with repository.open_file(target_path, "w") as f:
                    f.write(final_prompt)

    def _read_messages(self, file_path: str, repository: FileRepositoryPort) -> List[Dict[str, Any]]:
        messages = []
        
        # Regex to detect start of message
        # Android: 2/18/26, 07:07 - Author: Message
        # iOS: [2/18/26, 07:07:00] Author: Message
        timestamp_pattern = r'^(\d{1,2}/\d{1,2}/\d{2,4},? \d{1,2}:\d{2}|\[\d{1,2}/\d{1,2}/\d{2,4}.*?\])'
        
        try:
            with repository.open_file(file_path, 'r') as f:
                content = f.read()
            
            lines = content.splitlines()
            current_message = None
            
            for line in lines:
                if re.match(timestamp_pattern, line):
                    if current_message:
                        messages.append(current_message)
                    current_message = {"content": line}
                else:
                    if current_message:
                        current_message["content"] += "\n" + line
            
            if current_message:
                messages.append(current_message)
                
        except Exception:
            return []

        # Sort messages by timestamp
        messages.sort(key=self._parse_timestamp)
            
        return messages

    def _get_last_message(self, messages: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not messages:
            return None

        return messages[-1]

    def _parse_timestamp(self, msg: Dict[str, Any]) -> datetime:
        timestamp_pattern = r'^(\d{1,2}/\d{1,2}/\d{2,4},? \d{1,2}:\d{2}|\[\d{1,2}/\d{1,2}/\d{2,4}.*?\])'
        content = msg.get("content", "")
        match = re.match(timestamp_pattern, content)
        if not match:
            return datetime.min
        
        ts_str = match.group(1)
        # Normalize string for parsing
        # Remove brackets if iOS
        ts_str = ts_str.strip('[]')
        # Replace comma if Android
        ts_str = ts_str.replace(',', '')
        
        # Possible formats
        formats = [
            "%m/%d/%y %H:%M",       # 2/18/26 07:07
            "%m/%d/%Y %H:%M",       # 02/18/2026 07:07
            "%d/%m/%y %H:%M",       # 18/02/26 07:07
            "%d/%m/%Y %H:%M",       # 18/02/2026 07:07
            "%m/%d/%y %H:%M:%S",    # 2/18/26 07:07:00
            "%m/%d/%Y %H:%M:%S",
            "%d/%m/%y %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(ts_str, fmt)
            except ValueError:
                continue
        
        return datetime.min

    def _get_message_author(self, message: Dict[str, Any]) -> Optional[str]:
        line = message.get("content", "")
        # Regex for iOS: [dd/mm/yy HH:MM:SS] Author: Message
        # Regex for Android: dd/mm/yy HH:MM - Author: Message
        
        # Check for colon after timestamp pattern
        # Android: 12/10/2022 15:30 - Elias: Olá
        android_pattern = r'^\d{1,2}/\d{1,2}/\d{2,4},? \d{1,2}:\d{2}(?::\d{2})?(?: [AP]M)? - (.*?):'
        match = re.search(android_pattern, line)
        if match:
            return match.group(1)
            
        # iOS: [12/10/22 15:30:00] Elias: Olá
        ios_pattern = r'^\[.*?\] (.*?):'
        match = re.search(ios_pattern, line)
        if match:
            return match.group(1)
            
        return None

    def _is_message_unanswered(self, message: Dict[str, Any], whatsapp_account: Dict[str, Any]) -> bool:
        return not self._is_account_owner(message, whatsapp_account)

    def _is_account_owner(self, message: Dict[str, Any], whatsapp_account: Dict[str, Any]) -> bool:
        author = self._get_message_author(message)
        if not author:
            return False

        # Normalize names for comparison (strip, lower)
        author_norm = author.strip().lower()
        
        # 1. Check against Account ID (Phone Number)
        account_id = whatsapp_account.get("id")
        
        if account_id:
             # Clean ID: remove spaces, dashes, parens, plus
             # e.g. +55 (21) 9999-9999 -> 552199999999
             clean_id = re.sub(r'[\s\-\(\)\+]', '', account_id)
             # Clean Author: same normalization
             clean_author = re.sub(r'[\s\-\(\)\+]', '', author_norm)
             
             # Check if ID is present in author string (and ID is not empty)
             if clean_id and clean_id in clean_author:
                 return True # It is me
                 
             # Check reverse: if Author is present in ID string (e.g. Account has +55, Author doesn't)
             # Only if author is numeric and long enough (to avoid matching short names)
             if clean_author and clean_author.isdigit() and len(clean_author) >= 8 and clean_author in clean_id:
                 return True # It is me

        # 2. Check against Account Names
        account_names = whatsapp_account.get("names", [])
        for name in account_names:
            if name and name.strip().lower() in author_norm:
                return True # It is me

        # 3. Check common self-identifiers (export language dependent)
        self_identifiers = {"você", "you", "tu", "yo"}
        if author_norm in self_identifiers:
            return True

        return False # It is NOT me
