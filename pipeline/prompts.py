from pipeline.models import Character, Shot, Storyboard

REFERENCE_FRAMING = (
    "character reference portrait, head and shoulders, facing the camera, "
    "neutral plain background, even soft light, face clearly visible"
)
NEGATIVE_MOTION = (
    "blurry, distorted face, extra fingers, deformed hands, text, watermark, "
    "flicker, sudden cuts, fast motion"
)


def reference_prompt(character: Character, storyboard: Storyboard) -> str:
    return f"{character.description}. {REFERENCE_FRAMING}. {storyboard.style_block}"


def keyframe_prompt(shot: Shot, storyboard: Storyboard) -> str:
    cast = {character.id: character for character in storyboard.characters}
    descriptions = [cast[character_id].description for character_id in shot.characters]
    parts = [shot.keyframe.prompt, *descriptions, "subject centred in the frame", storyboard.style_block]
    return ". ".join(part.rstrip(". ") for part in parts)
