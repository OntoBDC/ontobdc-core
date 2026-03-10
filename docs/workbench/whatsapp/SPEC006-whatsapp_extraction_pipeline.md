# SPEC006 - WhatsApp Extraction Pipeline

## 1. Overview
This specification defines the pipeline for extracting, processing, and structuring WhatsApp chat data from exported ZIP archives. The process ensures data integrity, incremental updates, and compatibility with analysis tools (Excel, LLMs).

## 2. Extraction Pipeline

The `ExtractUnansweredWhatsappMessages` action orchestrates the following steps:

### 2.1. Decompression
- **Input**: A `.zip` file exported from WhatsApp (containing `_chat.txt` and attachments).
- **Action**: The `ZipArchiveAdapter` extracts the contents into a dedicated subdirectory named after the zip file (stripping the extension).
  - *Example*: `incoming/chat_export.zip` -> `incoming/chat_export/`
- **Rationale**: Prevents file clutter in the root directory and isolates attachments per conversation.

### 2.2. Chat File Identification
The pipeline searches for the chat log text file in the following order:
1. `Folder_Name.txt` (Exact match with folder name)
2. `_chat.txt` (Standard WhatsApp export name)

### 2.3. Incremental Processing
To support multiple imports of the same or updated conversations without duplication:
- **Existing Data**: The pipeline loads existing `messages.csv` if present.
- **Deduplication**: Each message generates a unique MD5 hash based on `timestamp + author + content`. Messages with existing hashes are skipped.
- **Versioning**: A `round` column tracks the import session. New imports increment the maximum existing round number.

### 2.4. Data Storage (Data Package)
Data is stored using the Frictionless Data Package standard, managed by `DataPackageAdapter`. All resources are saved in the `.__ontobdc__` hidden folder within the chat directory.

#### Resource: messages.csv
Main chat log.
- **Format**: CSV (UTF-8 with BOM for Excel compatibility).
- **Columns**:
  - `round`: Integer (Import session ID).
  - `data`: Date (YYYY-MM-DD).
  - `hora`: Time (HH:MM:SS).
  - `mensagem`: Raw message content.
  - `author`: Name of the sender.
  - `hash`: MD5 unique identifier.
  - `is_owner`: Boolean (True if sender matches the configured WhatsApp account).

#### Resource: attachments.csv
Inventory of all media files in the chat folder.
- **Columns**:
  - `round`: Integer.
  - `file_path`: Filename relative to the chat folder.
  - `content_size`: Size in bytes.
  - `created_at`: ISO timestamp.
  - `encoding_format`: MIME type (e.g., image/jpeg).
  - `hash`: MD5 of file content.

#### Resource: statistics.csv
Aggregated metrics per author (overwritten on each run).
- **Columns**:
  - `author`: Name.
  - `qtd_mensagens`: Total message count.
  - `max_delay_seconds`: Maximum time taken to reply to a previous message.
  - `last_message_at`: Timestamp of the last message sent.

### 2.5. Post-Processing
- **Source Archiving**: The processed source text file is renamed to `original_{file_hash}.txt` to prevent reprocessing and preserve the original artifact.
- **LLM Prompt Generation**: If the conversation is deemed "unanswered" (last message is NOT from the owner), an `analyze_chat.md` file is generated containing the context (last 20 messages) for LLM analysis.

## 3. Architecture

### Adapters
- **ZipArchiveAdapter**: Handles safe extraction to subfolders.
- **DataPackageAdapter**: Manages `datapackage.json` and CSV resources. Supports reading existing data and appending new records.

### Interfaces
- **FileRepositoryPort**: Extended with `exists(path)` and `rename(src, dst)` methods to support the pipeline logic.
