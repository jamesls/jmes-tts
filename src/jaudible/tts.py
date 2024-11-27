"""Performs text to speech using Amazon Polly."""

import time
import logging
from typing import Any, Optional

import boto3
from botocore.response import StreamingBody
from mypy_boto3_polly.literals import VoiceIdType, EngineType, LanguageCodeType
from mypy_boto3_polly.client import PollyClient
from mypy_boto3_s3.client import S3Client

from jaudible.voices import LANGUAGES


LOG = logging.getLogger(__name__)


def count_chars(contents: str):
    """Count number of characters billed by Polly.

    This is primarily to document what the actual calculation is more so
    than the calculation being complicated.  It didn't match exactly, but this
    was close enough.
    """
    return len(contents.strip())


def create_tts_client(
    contents: Optional[str] = None,
    filename: Optional[str] = None,
    bucket: Optional[str] = None,
    language: str = 'en',
) -> 'BaseTextToSpeech':
    if language not in LANGUAGES:
        raise ValueError(f"Invalid language: {language}")
    if contents is None and filename is None:
        raise ValueError("Either contents or filename must be provided")
    if filename is not None and bucket is None:
        raise ValueError("bucket must be provided when using filename")
    params = LANGUAGES[language]
    kwargs: dict[str, Any] = {**params}
    if filename is not None:
        assert bucket is not None
        kwargs['bucket'] = bucket
        cls = LongFormTextToSpeech
    else:
        cls = TextToSpeech
    return cls(**kwargs)


class BaseTextToSpeech:
    last_request_chars: int = 0

    def convert_to_speech(self, contents: str) -> StreamingBody:
        raise NotImplementedError("convert_to_speec")


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
    ) -> None:
        if polly_client is None:
            polly_client = boto3.client('polly')
        if s3_client is None:
            s3_client = boto3.client('s3')
        self._polly = polly_client
        self._s3 = s3_client
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
            time.sleep(self.DELAY)

    def _get_s3_download_stream(self, key: str):
        response = self._s3.get_object(Bucket=self.bucket, Key=key)
        return response['Body']
