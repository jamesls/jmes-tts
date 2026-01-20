"""Performs text to speech using Amazon Polly."""

import re
import time
import logging
from collections.abc import Callable
from typing import Any, Optional, get_args

import boto3
from botocore.response import StreamingBody
from mypy_boto3_polly.literals import VoiceIdType, EngineType, LanguageCodeType
from mypy_boto3_polly.client import PollyClient
from mypy_boto3_s3.client import S3Client

from jmestts.voices import LANGUAGES, normalize_language
from jmestts.pricing import PRICES


LOG = logging.getLogger(__name__)

MAX_SYNC_BILLABLE_CHARS = 3000


def list_polly_language_codes() -> tuple[str, ...]:
    codes = (str(code) for code in get_args(LanguageCodeType))
    return tuple(sorted(set(codes)))


def count_chars(contents: str) -> int:
    """Count number of characters billed by Polly.

    Polly strips leading/trailing whitespace and collapses consecutive
    whitespace characters into a single space.
    """
    text = contents.strip()
    text = re.sub(r'\s+', ' ', text)
    return len(text)


class TextTooLongError(ValueError):
    pass


class InvalidLanguageError(ValueError):
    language: str
    valid_languages: tuple[str, ...]

    def __init__(
        self, language: str, *, valid_languages: tuple[str, ...]
    ) -> None:
        self.language = language
        self.valid_languages = valid_languages
        valid_languages_str = ', '.join(valid_languages)
        super().__init__(
            f"Invalid language: {language}. "
            f"Valid languages: {valid_languages_str}. "
            "Run --list-languages to see presets and Polly codes."
        )


def validate_max_chars(
    contents: str, *, max_chars: int = MAX_SYNC_BILLABLE_CHARS
) -> None:
    billable_chars = count_chars(contents)
    if billable_chars <= max_chars:
        return

    raise TextTooLongError(
        f"Text is {billable_chars} billable characters, which exceeds the "
        f"max of {max_chars} for synchronous TTS. Provide --bucket to use "
        "long-form synthesis, or shorten your input."
    )


def resolve_tts_params(
    language: Optional[str] = None,
    *,
    voice: Optional[str] = None,
    engine: Optional[str] = None,
    language_code: Optional[str] = None,
) -> dict[str, Any]:
    # Use 'english' as default if no language specified
    effective_language = language if language is not None else 'english'
    normalized_language = normalize_language(effective_language)
    if normalized_language not in LANGUAGES:
        valid_languages = tuple(sorted(LANGUAGES))
        raise InvalidLanguageError(
            effective_language, valid_languages=valid_languages
        )
    params = LANGUAGES[normalized_language]
    kwargs: dict[str, Any] = {**params}

    if voice is not None:
        kwargs['voice'] = voice
    if engine is not None:
        kwargs['engine'] = engine
    if language_code is not None:
        kwargs['language_code'] = language_code

    return kwargs


def estimate_cost(*, engine: str, billable_chars: int) -> float:
    if engine not in PRICES:
        return 0.0
    return PRICES[engine] * billable_chars / 1_000_000


def create_tts_client(
    contents: Optional[str] = None,
    filename: Optional[str] = None,
    bucket: Optional[str] = None,
    language: Optional[str] = None,
    language_code: Optional[str] = None,
    voice: Optional[str] = None,
    engine: Optional[str] = None,
) -> 'BaseTextToSpeech':
    if (contents is None and filename is None) or (
        contents is not None and filename is not None
    ):
        raise ValueError(
            "Exactly one of contents or filename must be provided"
        )
    kwargs = resolve_tts_params(
        language, voice=voice, engine=engine, language_code=language_code
    )

    if bucket is not None:
        cls = LongFormTextToSpeech
        kwargs['bucket'] = bucket
    else:
        cls = TextToSpeech
    return cls(**kwargs)


class BaseTextToSpeech:
    last_request_chars: int = 0
    engine: EngineType

    def convert_to_speech(self, contents: str) -> StreamingBody:
        raise NotImplementedError("convert_to_speech")

    @property
    def last_cost(self) -> float:
        if self.engine not in PRICES:
            return 0.0
        return PRICES[self.engine] * self.last_request_chars / 1_000_000


class TextToSpeech(BaseTextToSpeech):
    """Converts text to speech using Amazon Polly."""

    def __init__(
        self,
        polly_client: PollyClient | None = None,
        voice: VoiceIdType = 'Matthew',
        engine: EngineType = 'generative',
        language_code: LanguageCodeType = 'en-US',
    ) -> None:
        if polly_client is None:
            polly_client = boto3.client('polly')
        self._polly = polly_client
        self.voice: VoiceIdType = voice
        self.engine: EngineType = engine
        self.language_code: LanguageCodeType = language_code
        self.last_request_chars = 0

    def convert_to_speech(self, contents: str) -> StreamingBody:
        """Converts text to speech."""
        validate_max_chars(contents)
        response = self._polly.synthesize_speech(
            Text=contents,
            OutputFormat='mp3',
            VoiceId=self.voice,
            Engine=self.engine,
            LanguageCode=self.language_code,
        )
        self.last_request_chars = response['RequestCharacters']
        return response['AudioStream']


class LongFormTextToSpeech(BaseTextToSpeech):
    """Converts long form text to speech using Amazon Polly.

    When the text content is over a given size (currently 3000 chars for
    standard voice), you need to use this class to generate audio.

    This has a larger max character size from 100k to 200k, depending
    on the engine used.

    This class requires an async workflow where a job is started and then
    results are uploaded to an S3 bucket.  This class abstracts all those
    details to still provide a blocking API that will automatically
    download the results from S3 when complete, so you have a similar
    API to the sync version of this class.
    """

    DELAY = 5

    def __init__(
        self,
        bucket: str,
        polly_client: PollyClient | None = None,
        s3_client: S3Client | None = None,
        voice: VoiceIdType = 'Matthew',
        engine: EngineType = 'generative',
        language_code: LanguageCodeType = 'en-US',
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        if polly_client is None:
            polly_client = boto3.client('polly')
        if s3_client is None:
            s3_client = boto3.client('s3')
        if sleep is None:
            sleep = time.sleep
        self._polly = polly_client
        self._s3 = s3_client
        self._sleep: Callable[[float], None] = sleep
        self.bucket = bucket
        self.voice: VoiceIdType = voice
        self.engine: EngineType = engine
        self.language_code: LanguageCodeType = language_code
        self.last_request_chars = 0

    def convert_to_speech(self, contents: str) -> StreamingBody:
        response = self._polly.start_speech_synthesis_task(
            Engine=self.engine,
            LanguageCode=self.language_code,
            OutputFormat='mp3',
            OutputS3BucketName=self.bucket,
            Text=contents,
            VoiceId=self.voice,
        )
        task_id = response['SynthesisTask']['TaskId']
        while True:
            # TODO: want to use waiters so we have timeouts/etc.
            result = self._polly.get_speech_synthesis_task(TaskId=task_id)
            status = result['SynthesisTask']['TaskStatus']
            if status == 'failed':
                raise RuntimeError(
                    f"TTS task failed, task_id={task_id}\n{result}"
                )
            elif status == 'completed':
                output_uri = result['SynthesisTask']['OutputUri']
                # The output uri is formatted as an https URL:
                # https://s3.us-east-1.amazonaws.com/jmes-tts/<pre>/<uuid>.mp3
                # So parse out the bucket and key.
                key = '/'.join(output_uri.split('/')[4:])
                stream = self._get_s3_download_stream(key)
                self.last_request_chars = result['SynthesisTask'][
                    'RequestCharacters'
                ]
                return stream
            self._sleep(self.DELAY)

    def _get_s3_download_stream(self, key: str):
        response = self._s3.get_object(Bucket=self.bucket, Key=key)
        return response['Body']
