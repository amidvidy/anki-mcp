from fastmcp import FastMCP
import requests
import random
import base64
import os
import tempfile
import numpy as np
from typing import Annotated, List, Tuple
from pydantic import Field

mcp_server = FastMCP("anki-mcp")

ANKI_CONNECT_URL = "http://localhost:8765"

@mcp_server.tool()
async def list_decks() -> str:
    """List all available Anki decks."""
    response = requests.post(ANKI_CONNECT_URL, json={
        "action": "deckNames",
        "version": 6
    })

    if response.status_code != 200:
        return f"Error: Failed to connect to Anki: {response.status_code}"

    result = response.json()
    if result.get("error"):
        return f"Error: {result['error']}"

    decks = result["result"]
    return f"Available decks ({len(decks)}):\n" + "\n".join(f"- {deck}" for deck in decks)

@mcp_server.tool()
async def get_deck_notes(
    deck_name: Annotated[str, Field(description="Name of the Anki deck to retrieve notes from")]
) -> str:
    """Get all notes/cards from a specific deck."""
    # First get all note IDs for the deck
    response = requests.post(ANKI_CONNECT_URL, json={
        "action": "findNotes",
        "version": 6,
        "params": {
            "query": f"deck:\"{deck_name}\""
        }
    })

    if response.status_code != 200:
        return f"Error: Failed to connect to Anki: {response.status_code}"

    result = response.json()
    if result.get("error"):
        return f"Error: {result['error']}"

    note_ids = result["result"]
    if not note_ids:
        return f"No notes found in deck '{deck_name}'"

    # Get note info for all notes
    response = requests.post(ANKI_CONNECT_URL, json={
        "action": "notesInfo",
        "version": 6,
        "params": {
            "notes": note_ids
        }
    })

    if response.status_code != 200:
        return f"Error: Failed to connect to Anki: {response.status_code}"

    result = response.json()
    if result.get("error"):
        return f"Error: {result['error']}"

    notes = result["result"]
    
    # Format the notes for better readability
    output = [f"Notes in deck '{deck_name}' ({len(notes)} total):\n"]
    
    for i, note in enumerate(notes, 1):
        output.append(f"Note {i} (ID: {note['noteId']}):")
        output.append(f"  Model: {note['modelName']}")
        output.append(f"  Tags: {', '.join(note['tags']) if note['tags'] else 'None'}")
        output.append("  Fields:")
        for field_name, field_value in note['fields'].items():
            # Truncate long field values for readability
            value = field_value['value'][:100] + "..." if len(field_value['value']) > 100 else field_value['value']
            output.append(f"    {field_name}: {value}")
        output.append("")
    
    return "\n".join(output)

@mcp_server.tool()
async def get_deck_sample(
    deck_name: Annotated[str, Field(description="Name of the Anki deck to sample notes from")],
    sample_size: Annotated[int, Field(description="Number of notes to randomly sample from the deck", ge=1, le=50)] = 5
) -> str:
    """Get a random sample of notes from a specific deck to understand typical note structure."""
    # First get all note IDs for the deck
    response = requests.post(ANKI_CONNECT_URL, json={
        "action": "findNotes",
        "version": 6,
        "params": {
            "query": f"deck:\"{deck_name}\""
        }
    })

    if response.status_code != 200:
        return f"Error: Failed to connect to Anki: {response.status_code}"

    result = response.json()
    if result.get("error"):
        return f"Error: {result['error']}"

    note_ids = result["result"]
    if not note_ids:
        return f"No notes found in deck '{deck_name}'"

    # Get a random sample of note IDs
    actual_sample_size = min(sample_size, len(note_ids))
    sampled_note_ids = random.sample(note_ids, actual_sample_size)

    # Get note info for sampled notes
    response = requests.post(ANKI_CONNECT_URL, json={
        "action": "notesInfo",
        "version": 6,
        "params": {
            "notes": sampled_note_ids
        }
    })

    if response.status_code != 200:
        return f"Error: Failed to connect to Anki: {response.status_code}"

    result = response.json()
    if result.get("error"):
        return f"Error: {result['error']}"

    notes = result["result"]
    
    # Format the notes for better readability
    output = [f"Sample of {len(notes)} notes from deck '{deck_name}' (total: {len(note_ids)}):\n"]
    
    for i, note in enumerate(notes, 1):
        output.append(f"Sample Note {i} (ID: {note['noteId']}):")
        output.append(f"  Model: {note['modelName']}")
        output.append(f"  Tags: {', '.join(note['tags']) if note['tags'] else 'None'}")
        output.append("  Fields:")
        for field_name, field_value in note['fields'].items():
            # Truncate long field values for readability
            value = field_value['value'][:200] + "..." if len(field_value['value']) > 200 else field_value['value']
            output.append(f"    {field_name}: {value}")
        output.append("")
    
    return "\n".join(output)

@mcp_server.tool()
async def get_deck_note_types(
    deck_name: Annotated[str, Field(description="Name of the Anki deck to analyze for note types")]
) -> str:
    """Get the note types (models) and their field definitions used in a specific deck."""
    # First get a sample of notes to find the note types used in this deck
    response = requests.post(ANKI_CONNECT_URL, json={
        "action": "findNotes",
        "version": 6,
        "params": {
            "query": f"deck:\"{deck_name}\""
        }
    })

    if response.status_code != 200:
        return f"Error: Failed to connect to Anki: {response.status_code}"

    result = response.json()
    if result.get("error"):
        return f"Error: {result['error']}"

    note_ids = result["result"]
    if not note_ids:
        return f"No notes found in deck '{deck_name}'"

    # Get info for a sample of notes to find unique model names
    sample_size = min(50, len(note_ids))  # Sample up to 50 notes to find model types
    sampled_note_ids = random.sample(note_ids, sample_size)
    
    response = requests.post(ANKI_CONNECT_URL, json={
        "action": "notesInfo",
        "version": 6,
        "params": {
            "notes": sampled_note_ids
        }
    })

    if response.status_code != 200:
        return f"Error: Failed to connect to Anki: {response.status_code}"

    result = response.json()
    if result.get("error"):
        return f"Error: {result['error']}"

    # Find unique model names used in this deck
    model_names = set()
    for note in result["result"]:
        model_names.add(note["modelName"])

    # Get field names for each model
    output = [f"Note types used in deck '{deck_name}':\n"]
    
    for model_name in sorted(model_names):
        response = requests.post(ANKI_CONNECT_URL, json={
            "action": "modelFieldNames",
            "version": 6,
            "params": {
                "modelName": model_name
            }
        })

        if response.status_code == 200:
            result = response.json()
            if not result.get("error"):
                fields = result["result"]
                output.append(f"Model: {model_name}")
                output.append(f"  Fields: {', '.join(fields)}")
                output.append("")

    return "\n".join(output)

@mcp_server.tool()
async def create_note(
    deck_name: Annotated[str, Field(description="Name of the Anki deck to add the note to")],
    model_name: Annotated[str, Field(description="Name of the note type/model to use for this note")],
    fields: Annotated[dict, Field(description="Dictionary mapping field names to their values (e.g., {'Front': 'Question', 'Back': 'Answer'})")],
    tags: Annotated[list, Field(description="Optional list of tags to add to the note")] = None
):
    """Create a new note in the specified deck with the given fields and tags."""
    if tags is None:
        tags = []

    note_data = {
        "deckName": deck_name,
        "modelName": model_name,
        "fields": fields,
        "tags": tags
    }

    response = requests.post(ANKI_CONNECT_URL, json={
        "action": "addNote",
        "version": 6,
        "params": {
            "note": note_data
        }
    })

    if response.status_code != 200:
        return {"error": f"Failed to connect to Anki: {response.status_code}"}

    result = response.json()
    if result.get("error"):
        return {"error": result["error"]}

    return {"noteId": result["result"], "success": True}

@mcp_server.tool()
async def update_note(
    note_id: Annotated[int, Field(description="ID of the note to update")],
    fields: Annotated[dict, Field(description="Dictionary mapping field names to their new values (e.g., {'Audio': '[sound:pronunciation.mp3]'})")],
    tags: Annotated[list, Field(description="Optional list of tags to replace existing tags")] = None
) -> dict:
    """Update specific fields of an existing note. Perfect for adding audio or other content to existing cards."""
    
    # First get the current note info to validate it exists and get current fields
    response = requests.post(ANKI_CONNECT_URL, json={
        "action": "notesInfo",
        "version": 6,
        "params": {
            "notes": [note_id]
        }
    })
    
    if response.status_code != 200:
        return {"error": f"Failed to connect to Anki: {response.status_code}", "success": False}
    
    result = response.json()
    if result.get("error"):
        return {"error": result["error"], "success": False}
    
    notes_info = result["result"]
    if not notes_info or not notes_info[0]:
        return {"error": f"Note with ID {note_id} not found", "success": False}
    
    current_note = notes_info[0]
    
    # Prepare the update - merge new fields with existing ones
    updated_fields = {}
    for field_name, field_data in current_note["fields"].items():
        # Keep existing field values
        updated_fields[field_name] = field_data["value"]
    
    # Update with new field values
    for field_name, new_value in fields.items():
        updated_fields[field_name] = new_value
    
    # Prepare note data for update
    note_data = {
        "id": note_id,
        "fields": updated_fields
    }
    
    # Add tags if provided, otherwise keep existing tags
    if tags is not None:
        note_data["tags"] = tags
    else:
        note_data["tags"] = current_note["tags"]
    
    # Update the note
    response = requests.post(ANKI_CONNECT_URL, json={
        "action": "updateNoteFields",
        "version": 6,
        "params": {
            "note": note_data
        }
    })
    
    if response.status_code != 200:
        return {"error": f"Failed to connect to Anki: {response.status_code}", "success": False}
    
    result = response.json()
    if result.get("error"):
        return {"error": result["error"], "success": False}
    
    return {
        "success": True,
        "note_id": note_id,
        "updated_fields": list(fields.keys()),
        "message": f"Successfully updated note {note_id} with fields: {', '.join(fields.keys())}"
    }

@mcp_server.tool()
async def create_deck_with_note_type(
    deck_name: Annotated[str, Field(description="Name for the new Anki deck to create")],
    model_name: Annotated[str, Field(description="Name for the note type/model to create or use")],
    fields: Annotated[list, Field(description="List of field names for the note type (e.g., ['Front', 'Back', 'Extra'])")],
    card_templates: Annotated[list, Field(description="Optional list of card template definitions. If not provided, basic front/back templates will be created")] = None
):
    """Create a new deck and optionally a new note type with specified fields and card templates."""
    
    # First create the deck
    response = requests.post(ANKI_CONNECT_URL, json={
        "action": "createDeck",
        "version": 6,
        "params": {
            "deck": deck_name
        }
    })

    if response.status_code != 200:
        return {"error": f"Failed to connect to Anki: {response.status_code}"}

    result = response.json()
    if result.get("error"):
        return {"error": f"Failed to create deck: {result['error']}"}

    deck_id = result["result"]

    # If we need to create a new note type (model)
    if card_templates is None:
        # Default card template for basic front/back cards
        card_templates = [
            {
                "Name": "Card 1",
                "Front": "{{" + fields[0] + "}}",
                "Back": "{{FrontSide}}<hr id=\"answer\">{{" + fields[1] + "}}" if len(fields) > 1 else "{{" + fields[0] + "}}"
            }
        ]

    # Check if model already exists
    response = requests.post(ANKI_CONNECT_URL, json={
        "action": "modelNames",
        "version": 6
    })

    existing_models = []
    if response.status_code == 200:
        result = response.json()
        if not result.get("error"):
            existing_models = result["result"]

    # Create new model if it doesn't exist
    if model_name not in existing_models:
        model_data = {
            "modelName": model_name,
            "inOrderFields": fields,
            "cardTemplates": card_templates,
            "css": ".card {\n font-family: arial;\n font-size: 20px;\n text-align: center;\n color: black;\n background-color: white;\n}\n"
        }

        response = requests.post(ANKI_CONNECT_URL, json={
            "action": "createModel",
            "version": 6,
            "params": model_data
        })

        if response.status_code != 200:
            return {"error": f"Failed to connect to Anki: {response.status_code}"}

        result = response.json()
        if result.get("error"):
            return {"error": f"Failed to create note type: {result['error']}"}

        return {
            "success": True,
            "deck_id": deck_id,
            "deck_name": deck_name,
            "model_created": True,
            "model_name": model_name,
            "fields": fields
        }
    else:
        return {
            "success": True,
            "deck_id": deck_id,
            "deck_name": deck_name,
            "model_created": False,
            "model_name": model_name,
            "message": f"Note type '{model_name}' already exists, deck created with existing note type"
        }

@mcp_server.tool()
async def list_note_types() -> str:
    """List all available note types (models) with their fields and card templates."""
    # Get all model names
    response = requests.post(ANKI_CONNECT_URL, json={
        "action": "modelNames",
        "version": 6
    })

    if response.status_code != 200:
        return f"Error: Failed to connect to Anki: {response.status_code}"

    result = response.json()
    if result.get("error"):
        return f"Error: {result['error']}"

    model_names = result["result"]
    output = [f"Available note types ({len(model_names)}):\n"]

    # Get detailed info for each model
    for model_name in sorted(model_names):
        output.append(f"Model: {model_name}")
        
        # Get field names
        response = requests.post(ANKI_CONNECT_URL, json={
            "action": "modelFieldNames",
            "version": 6,
            "params": {
                "modelName": model_name
            }
        })

        if response.status_code == 200:
            result = response.json()
            if not result.get("error"):
                fields = result["result"]
                output.append(f"  Fields: {', '.join(fields)}")

        # Get templates
        response = requests.post(ANKI_CONNECT_URL, json={
            "action": "modelTemplates",
            "version": 6,
            "params": {
                "modelName": model_name
            }
        })

        if response.status_code == 200:
            result = response.json()
            if not result.get("error"):
                templates = result["result"]
                output.append(f"  Templates: {len(templates)} card type(s)")
                for template in templates:
                    template_name = template.get("Name", "Unnamed")
                    output.append(f"    - {template_name}")

        # Get styling (CSS)
        response = requests.post(ANKI_CONNECT_URL, json={
            "action": "modelStyling",
            "version": 6,
            "params": {
                "modelName": model_name
            }
        })

        if response.status_code == 200:
            result = response.json()
            if not result.get("error"):
                css_length = len(result["result"]["css"])
                output.append(f"  CSS: {css_length} characters")
        
        output.append("")

    return "\n".join(output)

def _get_text_embedding(text: str, api_key: str) -> List[float]:
    """Get text embedding using OpenAI's embedding API."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "text-embedding-3-small",  # Cheaper and faster than ada-002
        "input": text
    }
    
    response = requests.post(
        "https://api.openai.com/v1/embeddings",
        headers=headers,
        json=data
    )
    
    if response.status_code != 200:
        raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")
    
    result = response.json()
    return result["data"][0]["embedding"]

def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

@mcp_server.tool()
async def generate_audio(
    text: Annotated[str, Field(description="Text to convert to speech")],
    language: Annotated[str, Field(description="Language code (e.g., 'cmn-cn' for Chinese, 'en-US' for English)")] = "cmn-cn",
    voice: Annotated[str, Field(description="Voice name (e.g., 'cmn-CN-Chirp3-HD-Achernar' for Chinese HD voice)")] = "cmn-CN-Chirp3-HD-Achernar"
) -> dict:
    """Generate audio file from text using Google Cloud Chirp TTS API and return base64 encoded audio data."""
    
    # Get Google Cloud API key from environment variable
    api_key = os.getenv("GOOGLE_CLOUD_API_KEY")
    if not api_key:
        return {
            "error": "Google Cloud API key not found. Please set GOOGLE_CLOUD_API_KEY environment variable.",
            "success": False,
            "setup_instructions": "Run: export GOOGLE_CLOUD_API_KEY='your-api-key-here'"
        }
    
    try:
        # Google Cloud TTS API call with API key as query parameter
        data = {
            "input": {"text": text},
            "voice": {
                "languageCode": language,
                "name": voice
            },
            "audioConfig": {
                "audioEncoding": "MP3"
            }
        }
        
        response = requests.post(
            f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}",
            headers={"Content-Type": "application/json"},
            json=data
        )
        
        if response.status_code != 200:
            return {
                "error": f"Google Cloud TTS API error: {response.status_code} - {response.text}",
                "success": False
            }
        
        result = response.json()
        audio_base64 = result["audioContent"]
        
        return {
            "success": True,
            "audio_base64": audio_base64,
            "format": "mp3",
            "language": language,
            "voice": voice,
            "text": text,
            "model": "chirp"
        }
        
    except Exception as e:
        return {
            "error": f"Failed to generate audio: {str(e)}",
            "success": False
        }

@mcp_server.tool()
async def create_notes_bulk(
    deck_name: Annotated[str, Field(description="Name of the Anki deck to add notes to")],
    notes_list: Annotated[list, Field(description="List of note dictionaries, each containing 'model_name', 'fields', and optionally 'tags'")]
) -> dict:
    """Create multiple notes in a single batch operation for efficiency."""
    if not notes_list:
        return {"error": "No notes provided", "success": False}
    
    # Prepare notes for Anki
    anki_notes = []
    for i, note_data in enumerate(notes_list):
        if not isinstance(note_data, dict):
            return {"error": f"Note {i+1} is not a dictionary", "success": False}
        
        if "model_name" not in note_data or "fields" not in note_data:
            return {"error": f"Note {i+1} missing required 'model_name' or 'fields'", "success": False}
        
        anki_note = {
            "deckName": deck_name,
            "modelName": note_data["model_name"],
            "fields": note_data["fields"],
            "tags": note_data.get("tags", [])
        }
        anki_notes.append(anki_note)
    
    # Use Anki's addNotes action for bulk creation
    response = requests.post(ANKI_CONNECT_URL, json={
        "action": "addNotes",
        "version": 6,
        "params": {
            "notes": anki_notes
        }
    })
    
    if response.status_code != 200:
        return {"error": f"Failed to connect to Anki: {response.status_code}", "success": False}
    
    result = response.json()
    if result.get("error"):
        return {"error": result["error"], "success": False}
    
    note_ids = result["result"]
    successful_notes = [note_id for note_id in note_ids if note_id is not None]
    failed_count = len([note_id for note_id in note_ids if note_id is None])
    
    return {
        "success": True,
        "total_attempted": len(notes_list),
        "successful_count": len(successful_notes),
        "failed_count": failed_count,
        "note_ids": note_ids,
        "message": f"Successfully created {len(successful_notes)} out of {len(notes_list)} notes"
    }

@mcp_server.tool()
async def save_media_file(
    filename: Annotated[str, Field(description="Name of the file to save (e.g., 'audio.mp3', 'image.jpg')")],
    base64_data: Annotated[str, Field(description="Base64 encoded file data")],
    media_type: Annotated[str, Field(description="Type of media file (audio, image, etc.)")] = "audio"
) -> dict:
    """Save base64 encoded media data as a file in Anki's media collection for use in cards."""
    
    try:
        # Use AnkiConnect's storeMediaFile action to save the base64 data
        response = requests.post(ANKI_CONNECT_URL, json={
            "action": "storeMediaFile",
            "version": 6,
            "params": {
                "filename": filename,
                "data": base64_data
            }
        })
        
        if response.status_code != 200:
            return {
                "error": f"Failed to connect to Anki: {response.status_code}",
                "success": False
            }
        
        result = response.json()
        if result.get("error"):
            return {
                "error": result["error"],
                "success": False
            }
        
        # AnkiConnect returns the filename that was actually used (may be modified to avoid conflicts)
        saved_filename = result["result"]
        
        return {
            "success": True,
            "filename": saved_filename,
            "media_type": media_type,
            "message": f"Media file saved as '{saved_filename}' in Anki's media collection"
        }
        
    except Exception as e:
        return {
            "error": f"Failed to save media file: {str(e)}",
            "success": False
        }

@mcp_server.tool()
async def generate_and_save_audio(
    text: Annotated[str, Field(description="Text to convert to speech and save")],
    filename: Annotated[str, Field(description="Name for the audio file (e.g., 'pronunciation.mp3')")],
    language: Annotated[str, Field(description="Language code (e.g., 'cmn-cn' for Chinese, 'en-US' for English)")] = "cmn-cn",
    voice: Annotated[str, Field(description="Voice name (e.g., 'cmn-CN-Chirp3-HD-Achernar' for Chinese HD voice)")] = "cmn-CN-Chirp3-HD-Achernar"
) -> dict:
    """Generate audio from text and save it to Anki's media collection, returning filename for use in cards."""
    
    # First generate the audio
    audio_result = await generate_audio(text, language, voice)
    
    if not audio_result.get("success"):
        return audio_result
    
    # Then save it to Anki's media collection
    save_result = await save_media_file(filename, audio_result["audio_base64"], "audio")
    
    if not save_result.get("success"):
        return save_result
    
    return {
        "success": True,
        "filename": save_result["filename"],
        "text": text,
        "language": language,
        "voice": voice,
        "sound_tag": f"[sound:{save_result['filename']}]",
        "message": f"Audio generated and saved as '{save_result['filename']}'. Use [sound:{save_result['filename']}] in your card fields."
    }

@mcp_server.tool()
async def update_notes_bulk(
    updates: Annotated[list, Field(description="List of update dictionaries, each containing 'note_id', 'fields' dict, and optionally 'tags' list")]
) -> dict:
    """Update multiple notes in a single batch operation for efficiency. Each update should contain note_id and fields to update."""
    if not updates:
        return {"error": "No updates provided", "success": False}
    
    successful_updates = []
    failed_updates = []
    
    for i, update_data in enumerate(updates):
        if not isinstance(update_data, dict):
            failed_updates.append({
                "index": i,
                "error": "Update data is not a dictionary",
                "data": update_data
            })
            continue
        
        if "note_id" not in update_data or "fields" not in update_data:
            failed_updates.append({
                "index": i,
                "error": "Missing required 'note_id' or 'fields'",
                "data": update_data
            })
            continue
        
        # Use the existing update_note function for each update
        try:
            result = await update_note(
                note_id=update_data["note_id"],
                fields=update_data["fields"],
                tags=update_data.get("tags")
            )
            
            if result.get("success"):
                successful_updates.append({
                    "note_id": update_data["note_id"],
                    "updated_fields": result["updated_fields"]
                })
            else:
                failed_updates.append({
                    "index": i,
                    "note_id": update_data["note_id"],
                    "error": result.get("error", "Unknown error"),
                    "data": update_data
                })
        except Exception as e:
            failed_updates.append({
                "index": i,
                "note_id": update_data.get("note_id", "unknown"),
                "error": str(e),
                "data": update_data
            })
    
    return {
        "success": True,
        "total_attempted": len(updates),
        "successful_count": len(successful_updates),
        "failed_count": len(failed_updates),
        "successful_updates": successful_updates,
        "failed_updates": failed_updates,
        "message": f"Successfully updated {len(successful_updates)} out of {len(updates)} notes"
    }

@mcp_server.tool()
async def find_similar_notes(
    deck_name: Annotated[str, Field(description="Name of the Anki deck to search in")],
    search_text: Annotated[str, Field(description="Text to search for (e.g., hanzi, word, or phrase)")],
    similarity_threshold: Annotated[float, Field(description="Minimum similarity score (0.0-1.0, default 0.7)", ge=0.0, le=1.0)] = 0.7,
    max_results: Annotated[int, Field(description="Maximum number of similar notes to return", ge=1, le=50)] = 10
) -> dict:
    """Find notes with similar semantic content using vector embeddings, works well with Chinese text."""
    
    # Get API key for embeddings
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "error": "OpenAI API key not found. Please set OPENAI_API_KEY environment variable.",
            "success": False,
            "setup_instructions": "Run: export OPENAI_API_KEY='your-api-key-here' or add it to your .env file"
        }
    
    try:
        # Get all notes from the deck first
        response = requests.post(ANKI_CONNECT_URL, json={
            "action": "findNotes",
            "version": 6,
            "params": {
                "query": f"deck:\"{deck_name}\""
            }
        })
        
        if response.status_code != 200:
            return {"error": f"Failed to connect to Anki: {response.status_code}", "success": False}
        
        result = response.json()
        if result.get("error"):
            return {"error": result["error"], "success": False}
        
        note_ids = result["result"]
        if not note_ids:
            return {"error": f"No notes found in deck '{deck_name}'", "success": False}
        
        # Get detailed info for all notes
        response = requests.post(ANKI_CONNECT_URL, json={
            "action": "notesInfo",
            "version": 6,
            "params": {
                "notes": note_ids
            }
        })
        
        if response.status_code != 200:
            return {"error": f"Failed to connect to Anki: {response.status_code}", "success": False}
        
        result = response.json()
        if result.get("error"):
            return {"error": result["error"], "success": False}
        
        notes = result["result"]
        
        # Get embedding for search text
        search_embedding = _get_text_embedding(search_text, api_key)
        
        # Calculate similarities
        similarities = []
        for note in notes:
            # Combine all field values for embedding comparison
            combined_text = " ".join([
                field_data["value"] for field_data in note["fields"].values() 
                if field_data["value"].strip()
            ])
            
            if not combined_text.strip():
                continue
                
            try:
                note_embedding = _get_text_embedding(combined_text, api_key)
                similarity = _cosine_similarity(search_embedding, note_embedding)
                
                if similarity >= similarity_threshold:
                    similarities.append({
                        "note": note,
                        "similarity": similarity,
                        "combined_text": combined_text
                    })
            except Exception as e:
                # Skip notes that fail embedding generation
                continue
        
        # Sort by similarity (highest first) and limit results
        similarities.sort(key=lambda x: x["similarity"], reverse=True)
        similarities = similarities[:max_results]
        
        if not similarities:
            return {
                "success": True,
                "found_count": 0,
                "message": f"No notes found with similarity >= {similarity_threshold} to '{search_text}' in deck '{deck_name}'",
                "notes": []
            }
        
        # Format results
        formatted_notes = []
        for item in similarities:
            note = item["note"]
            formatted_note = {
                "note_id": note["noteId"],
                "model_name": note["modelName"],
                "tags": note["tags"],
                "similarity_score": round(item["similarity"], 4),
                "fields": {}
            }
            
            for field_name, field_data in note["fields"].items():
                formatted_note["fields"][field_name] = field_data["value"]
            
            formatted_notes.append(formatted_note)
        
        return {
            "success": True,
            "search_text": search_text,
            "found_count": len(similarities),
            "similarity_threshold": similarity_threshold,
            "deck_name": deck_name,
            "notes": formatted_notes
        }
        
    except Exception as e:
        return {
            "error": f"Failed to find similar notes: {str(e)}",
            "success": False
        }

if __name__ == "__main__":
    mcp_server.run()
