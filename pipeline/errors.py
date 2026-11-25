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
        super().__init__("FFmpeg not found. Run: make install (it comes with the imageio-ffmpeg package)")
