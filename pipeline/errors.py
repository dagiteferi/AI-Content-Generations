class PipelineError(Exception):
    """An expected failure with a message that tells the user what to do next."""


class MissingCredential(PipelineError):
    def __init__(self, env_var: str) -> None:
        super().__init__(f"{env_var} is not set. Add it to .env (see .env.example).")


class ConsentError(PipelineError):
    pass


class StageError(PipelineError):
    pass


class FFmpegMissing(PipelineError):
    def __init__(self) -> None:
        super().__init__("ffmpeg/ffprobe not found. Install it: sudo apt install ffmpeg")
