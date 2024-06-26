"""Performs text to speech using Amazon Polly."""

import time
import logging

import boto3


LOG = logging.getLogger(__name__)


def convert_to_audio(contents: str):
    client = boto3.client('polly')
    response = client.synthesize_speech(
        Text=contents,
        OutputFormat='mp3',
        VoiceId='Matthew',
        Engine='generative',
        LanguageCode='en-US',
    )
    num_chars = response['RequestCharacters']
    stream = response['AudioStream']
    print(f"Total request chars: {num_chars}")
    return stream


def count_chars(contents: str):
    """Count number of characters billed by Polly.

    This is primarily to document what the actual calculation is more so
    than the calculation being complicated.  It didn't match exactly, but this
    was close enough.
    """
    return len(contents.strip())


class TextToSpeech:
    """Converts text to speech using Amazon Polly."""

    # The docs say the cutoff is 3000, we add a buffer to be safe.
    SYNC_SIZE_CUTOFF = 2900
    DELAY = 5

    def __init__(
        self,
        bucket: str,
        session=None,
        voice: str = 'Matthew',
        engine: str = 'generative',
    ) -> None:
        if session is None:
            session = boto3.Session()
        self.session = session
        self._polly = self.session.client('polly')
        self._s3 = self.session.client('s3')
        self.bucket = bucket
        self.voice = voice
        # engine is of type `str`, but we assert the type here so
        # self.engine is of type Literal['generative', 'long-form', 'neural', 'standard'].
        assert engine in ('generative', 'long-form', 'neural', 'standard')
        self.engine = engine
        self.last_request_chars = 0

    def convert_to_speech(self, contents: str):
        """Converts text to speech.

        This supports long form text using the async speech
        synthesis task if needed.
        """
        num_chars = count_chars(contents)
        if num_chars < self.SYNC_SIZE_CUTOFF:
            return self._convert_sync(contents)
        else:
            return self._convert_async(contents)

    def _convert_sync(self, contents: str):
        response = self._polly.synthesize_speech(
            Text=contents,
            OutputFormat='mp3',
            VoiceId=self.voice,
            Engine=self.engine,
            LanguageCode='en-US',
        )
        self.last_request_chars = response['RequestCharacters']
        return response['AudioStream']

    def _convert_async(self, contents: str):
        if not self.bucket:
            raise RuntimeError(
                "The `bucket` parameter is required for large text"
            )
        response = self._polly.start_speech_synthesis_task(
            Engine=self.engine,
            LanguageCode='en-US',
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
