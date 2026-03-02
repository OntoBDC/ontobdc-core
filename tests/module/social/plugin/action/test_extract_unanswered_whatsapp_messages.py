
import unittest
import sys
import os
from unittest.mock import MagicMock, patch, mock_open
from typing import List, Dict, Any

# Ensure we can import from the project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../../../")))

from ontobdc.module.social.plugin.action.extract_unanswered_whatsapp_messages import ExtractUnansweredWhatsappMessages
from ontobdc.module.resource.domain.port.repository import FileRepositoryPort

class TestExtractUnansweredWhatsappMessages(unittest.TestCase):
    
    def setUp(self):
        self.action = ExtractUnansweredWhatsappMessages()
        # Use a flexible mock since FileRepositoryPort definition might be missing list_files
        # or the code uses a concrete implementation method.
        self.mock_repository = MagicMock() 

    def test_read_messages_multiline_android(self):
        """Test reading multi-line messages with Android timestamp format."""
        content = """2/18/26, 07:07 - Elias Magalhães: Olá. Aqui é a Ada, assistente virtual do Elias.
Eu posso te ajudar coletando as informações necessárias até o Elias retornar.
Pode me dizer objetivamente o que você precisa?
2/18/26, 07:08 - Other: Ok, thanks."""
        
        print("\n--- Testing _read_messages (Android Multiline) ---")
        
        # Setup mock repository.open_file
        mock_file = mock_open(read_data=content)
        self.mock_repository.open_file.return_value = mock_file()
        
        messages = self.action._read_messages("dummy_path.txt", self.mock_repository)
            
        self.assertEqual(len(messages), 2)
        
        # Verify first message content (merged)
        first_msg = messages[0]["content"]
        print(f"Msg 1: {first_msg[:50]}... [len={len(first_msg)}]")
        self.assertIn("Olá. Aqui é a Ada", first_msg)
        self.assertIn("Pode me dizer objetivamente", first_msg)
        
        # Verify second message
        second_msg = messages[1]["content"]
        print(f"Msg 2: {second_msg}")
        self.assertIn("Ok, thanks", second_msg)

    def test_read_messages_ios(self):
        """Test reading messages with iOS timestamp format."""
        content = """[2/18/26, 07:07:00] Elias: Hello
[2/18/26, 07:08:00] Other: Hi there"""
        
        print("\n--- Testing _read_messages (iOS) ---")
        
        # Setup mock repository.open_file
        mock_file = mock_open(read_data=content)
        self.mock_repository.open_file.return_value = mock_file()
        
        messages = self.action._read_messages("dummy_path.txt", self.mock_repository)
            
        self.assertEqual(len(messages), 2)
        print(f"Msg 1: {messages[0]['content']}")
        print(f"Msg 2: {messages[1]['content']}")

    def test_read_messages_sorting(self):
        """Test that messages are sorted chronologically."""
        content = """2/18/26, 08:00 - Elias: Second message
2/18/26, 07:07 - Elias: First message
2/18/26, 09:30 - Elias: Third message"""
        
        print("\n--- Testing _read_messages (Sorting) ---")
        
        # Setup mock repository.open_file
        mock_file = mock_open(read_data=content)
        self.mock_repository.open_file.return_value = mock_file()
        
        messages = self.action._read_messages("dummy_path.txt", self.mock_repository)
            
        self.assertEqual(len(messages), 3)
        
        # Check order
        print(f"Msg 1: {messages[0]['content']}")
        print(f"Msg 2: {messages[1]['content']}")
        print(f"Msg 3: {messages[2]['content']}")
        
        self.assertIn("07:07", messages[0]["content"])
        self.assertIn("08:00", messages[1]["content"])
        self.assertIn("09:30", messages[2]["content"])

    def test_extract_messages(self):
        """Test extracting messages from a folder."""
        folder_path = "/tmp/extracted/WhatsApp Chat with X"
        expected_file_path = "/tmp/extracted/WhatsApp Chat with X/WhatsApp Chat with X.txt"
        
        # Mock repository.exists to return True
        self.mock_repository.exists.return_value = True
        
        # Mock get_json to return None (simulating new package) or a dict
        self.mock_repository.get_json.return_value = None
        
        # Mock open_file for both reading messages and saving datapackage.json
        # We need side_effect to handle different files differently if needed, 
        # but for now we can just return a mock that supports context manager and write.
        mock_file_obj = MagicMock()
        mock_file_obj.__enter__.return_value = mock_file_obj
        mock_file_obj.read.return_value = "mocked content" # content for _read_messages
        self.mock_repository.open_file.return_value = mock_file_obj
        
        print(f"\n--- Testing _extract_messages ---")
        print(f"Folder: {folder_path}")
        print(f"Expected File: {expected_file_path}")
        
        # Mock _read_messages to verify it gets called with the correct path
        with patch.object(self.action, '_read_messages', return_value=[{"content": "mocked"}]) as mock_read:
            messages = self.action._extract_messages(folder_path, self.mock_repository)
            
            print(f"Extracted count: {len(messages)}")
            if len(messages) > 0:
                print(f"Sample: {messages[0]}")
            
            self.assertEqual(len(messages), 1)
            mock_read.assert_called_once_with(expected_file_path, self.mock_repository)
            
            # Verify save was called (file write)
            # Since we mocked open_file, we can check calls.
            # Expect calls: 
            # 1. Reading messages (handled by _read_messages mock, so actually NOT called on repo if mocked)
            #    Wait, we mocked self.action._read_messages, so the real _read_messages is NOT called.
            #    So open_file is NOT called for reading messages.
            # 2. Saving datapackage.json (called by dp_adapter.save())
            
            # Check if open_file was called with 'w' mode for datapackage.json
            expected_dp_path = f"{folder_path}/datapackage.json"
            self.mock_repository.open_file.assert_called_with(expected_dp_path, "w")

if __name__ == '__main__':
    unittest.main()
