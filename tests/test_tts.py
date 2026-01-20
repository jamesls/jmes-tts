from collections.abc import Callable
from io import BytesIO

import boto3
import pytest
from botocore.stub import Stubber

from jmestts import tts


@pytest.fixture(autouse=True)
def mock_aws_credentials(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_REGION", "us-east-1")


@pytest.fixture
def noop_sleep() -> Callable[[float], None]:
    def noop(_: float) -> None:
        return None

    return noop


@pytest.fixture
def polly_client_stub():
    polly_client = boto3.client('polly', region_name='us-east-1')
    stubber = Stubber(polly_client)
    stubber.activate()
    yield polly_client, stubber
    stubber.deactivate()


@pytest.fixture
def s3_client_stub():
    s3_client = boto3.client('s3', region_name='us-east-1')
    stubber = Stubber(s3_client)
    stubber.activate()
    yield s3_client, stubber
    stubber.deactivate()


# Test for count_chars function


@pytest.mark.parametrize(
    "input_text, expected_count",
    [
        ("Hello World", 11),
        ("", 0),
        ("A" * 100, 100),
        ("\n\t ", 0),
        # Consecutive spaces collapsed to single space
        ("Hello  World", 11),
        ("Hello    World", 11),
        # Tabs collapsed to single space
        ("Hello\tWorld", 11),
        ("Hello\t\tWorld", 11),
        # Newlines collapsed to single space
        ("Hello\nWorld", 11),
        ("Hello\n\nWorld", 11),
        # Mixed whitespace collapsed to single space
        ("Hello \t\n World", 11),
        ("One  Two   Three", 13),
        # Leading/trailing whitespace with internal collapse
        ("  Hello  World  ", 11),
        ("\n\tHello\t\tWorld\n\t", 11),
    ],
)
def test_count_chars(input_text, expected_count):
    assert tts.count_chars(input_text) == expected_count


def test_validate_max_chars_uses_billable_chars():
    contents = "A" + (" " * 4000) + "B"
    tts.validate_max_chars(contents)


def test_validate_max_chars_over_limit_raises_helpful_error():
    contents = "A" * (tts.MAX_SYNC_BILLABLE_CHARS + 1)
    with pytest.raises(
        tts.TextTooLongError,
        match=r"Text is 3001 billable characters.*max of 3000.*--bucket",
    ):
        tts.validate_max_chars(contents)


def test_tts_convert_to_speech_over_limit_errors(polly_client_stub):
    polly_client, _ = polly_client_stub
    tts_client = tts.TextToSpeech(polly_client=polly_client)
    contents = "A" * (tts.MAX_SYNC_BILLABLE_CHARS + 1)
    with pytest.raises(tts.TextTooLongError, match=r"max of 3000"):
        tts_client.convert_to_speech(contents)


def test_resolve_tts_params_overrides_voice_and_engine():
    resolved = tts.resolve_tts_params(
        " English ", voice="Joanna", engine="standard"
    )
    assert resolved["voice"] == "Joanna"
    assert resolved["engine"] == "standard"
    assert resolved["language_code"] == "en-US"


def test_estimate_cost_unknown_engine_is_zero():
    assert (
        tts.estimate_cost(engine="unknown_engine", billable_chars=1000) == 0.0
    )


def test_tts_convert_to_speech(polly_client_stub):
    polly_client, stubber = polly_client_stub
    test_text = "Hello, this is a test."
    expected_params = {
        'Text': test_text,
        'OutputFormat': 'mp3',
        'VoiceId': 'Matthew',
        'Engine': 'generative',
        'LanguageCode': 'en-US',
    }
    mock_stream = BytesIO(b"fake audio data")
    response = {
        'RequestCharacters': len(test_text),
        'AudioStream': mock_stream,
    }
    stubber.add_response('synthesize_speech', response, expected_params)

    tts_client = tts.TextToSpeech(polly_client=polly_client)
    stream = tts_client.convert_to_speech(test_text)

    assert stream.read() == b"fake audio data"
    assert tts_client.last_request_chars == len(test_text)


def test_long_form_tts_convert_to_speech(
    polly_client_stub, s3_client_stub, noop_sleep
):
    polly_client, polly_stubber = polly_client_stub
    s3_client, s3_stubber = s3_client_stub
    bucket_name = "test-bucket"
    test_text = (
        "This is a long form text." * 200
    )  # Ensures over 3000 chars if needed

    # Mock response for start_speech_synthesis_task
    start_response = {
        'SynthesisTask': {
            'TaskId': 'test-task-id',
            'TaskStatus': 'inProgress',
            'OutputUri': (
                f"https://s3.us-east-1.amazonaws.com/{bucket_name}/"
                "path/to/output.mp3"
            ),
            'RequestCharacters': len(test_text),
        }
    }
    start_params = {
        'Engine': 'generative',
        'LanguageCode': 'en-US',
        'OutputFormat': 'mp3',
        'OutputS3BucketName': bucket_name,
        'Text': test_text,
        'VoiceId': 'Matthew',
    }
    polly_stubber.add_response(
        'start_speech_synthesis_task', start_response, start_params
    )

    # Mock response for get_speech_synthesis_task (first call: inProgress)
    get_response_in_progress = {
        'SynthesisTask': {
            'TaskId': 'test-task-id',
            'TaskStatus': 'inProgress',
            'OutputUri': (
                f"https://s3.us-east-1.amazonaws.com/{bucket_name}"
                "/path/to/output.mp3"
            ),
            'RequestCharacters': len(test_text),
        }
    }
    # Mock response for get_speech_synthesis_task (second call: completed)
    get_response_completed = {
        'SynthesisTask': {
            'TaskId': 'test-task-id',
            'TaskStatus': 'completed',
            'OutputUri': (
                f"https://s3.us-east-1.amazonaws.com/{bucket_name}"
                "/path/to/output.mp3"
            ),
            'RequestCharacters': len(test_text),
        }
    }
    get_params = {
        'TaskId': 'test-task-id',
    }
    polly_stubber.add_response(
        'get_speech_synthesis_task', get_response_in_progress, get_params
    )
    polly_stubber.add_response(
        'get_speech_synthesis_task', get_response_completed, get_params
    )

    # Mock response for s3.get_object
    s3_key = "path/to/output.mp3"
    s3_response = {
        'Body': BytesIO(b"fake long form audio data"),
    }
    s3_stubber.add_response(
        'get_object',
        s3_response,
        {
            'Bucket': bucket_name,
            'Key': s3_key,
        },
    )

    # Initialize the testable LongFormTextToSpeech with stubbed clients
    tts_client = tts.LongFormTextToSpeech(
        bucket=bucket_name,
        polly_client=polly_client,
        s3_client=s3_client,
        sleep=noop_sleep,
    )

    stream = tts_client.convert_to_speech(test_text)

    assert stream.read() == b"fake long form audio data"
    assert tts_client.last_request_chars == len(test_text)


def test_long_form_tts_task_failure(
    polly_client_stub, s3_client_stub, noop_sleep
):
    polly_client, polly_stubber = polly_client_stub
    s3_client, _ = s3_client_stub
    bucket_name = "test-bucket"
    test_text = "This is a long form text." * 200
    start_response = {
        'SynthesisTask': {
            'TaskId': 'test-task-id',
            'TaskStatus': 'inProgress',
            'OutputUri': (
                f"https://s3.us-east-1.amazonaws.com/{bucket_name}"
                "/path/to/output.mp3"
            ),
            'RequestCharacters': len(test_text),
        }
    }
    start_params = {
        'Engine': 'generative',
        'LanguageCode': 'en-US',
        'OutputFormat': 'mp3',
        'OutputS3BucketName': bucket_name,
        'Text': test_text,
        'VoiceId': 'Matthew',
    }
    polly_stubber.add_response(
        'start_speech_synthesis_task', start_response, start_params
    )

    # Mock response for get_speech_synthesis_task indicating failure
    get_response_failed = {
        'SynthesisTask': {
            'TaskId': 'test-task-id',
            'TaskStatus': 'failed',
            'OutputUri': (
                f"https://s3.us-east-1.amazonaws.com/{bucket_name}"
                "/path/to/output.mp3"
            ),
            'RequestCharacters': len(test_text),
        }
    }
    get_params = {
        'TaskId': 'test-task-id',
    }
    polly_stubber.add_response(
        'get_speech_synthesis_task', get_response_failed, get_params
    )

    # Initialize the testable LongFormTextToSpeech with stubbed clients
    tts_client = tts.LongFormTextToSpeech(
        bucket=bucket_name,
        polly_client=polly_client,
        s3_client=s3_client,
        sleep=noop_sleep,
    )

    with pytest.raises(RuntimeError, match="TTS task failed"):
        tts_client.convert_to_speech(test_text)


# Test for create_tts_client function


def test_create_tts_client_with_contents_only():
    client = tts.create_tts_client(contents="Hello world")
    assert isinstance(client, tts.TextToSpeech)
    assert client.voice == 'Matthew'
    assert client.engine == 'generative'
    assert client.language_code == 'en-US'


def test_create_tts_client_with_bucket():
    client = tts.create_tts_client(
        contents="Hello world", bucket="test-bucket"
    )
    assert isinstance(client, tts.LongFormTextToSpeech)
    assert client.bucket == "test-bucket"
    assert client.voice == 'Matthew'
    assert client.engine == 'generative'
    assert client.language_code == 'en-US'


def test_create_tts_client_with_different_language():
    client = tts.create_tts_client(contents="Bonjour", language='french')
    assert isinstance(client, tts.TextToSpeech)
    assert client.voice == 'Lea'
    assert client.engine == 'generative'
    assert client.language_code == 'fr-FR'


def test_create_tts_client_invalid_language():
    with pytest.raises(ValueError, match="Invalid language: invalid_lang"):
        tts.create_tts_client(contents="Hello", language='invalid_lang')


def test_create_tts_client_no_contents_or_filename():
    with pytest.raises(
        ValueError,
        match="Exactly one of contents or filename must be provided",
    ):
        tts.create_tts_client(language='english')


def test_last_cost_calculation(polly_client_stub):
    polly_client, stubber = polly_client_stub
    test_text = "Hello" * 100  # 500 chars

    expected_params = {
        'Text': test_text,
        'OutputFormat': 'mp3',
        'VoiceId': 'Matthew',
        'Engine': 'generative',
        'LanguageCode': 'en-US',
    }
    mock_stream = BytesIO(b"fake audio data")
    response = {
        'RequestCharacters': 500,
        'AudioStream': mock_stream,
    }
    stubber.add_response('synthesize_speech', response, expected_params)

    tts_client = tts.TextToSpeech(polly_client=polly_client)
    tts_client.convert_to_speech(test_text)

    expected_cost = 30 * 500 / 1_000_000
    assert tts_client.last_cost == expected_cost


def test_last_cost_unknown_engine():
    tts_client = tts.TextToSpeech()
    tts_client.engine = 'unknown_engine'
    tts_client.last_request_chars = 1000
    assert tts_client.last_cost == 0.0


def test_text_to_speech_custom_params(polly_client_stub):
    polly_client, stubber = polly_client_stub
    test_text = "Hello world"

    expected_params = {
        'Text': test_text,
        'OutputFormat': 'mp3',
        'VoiceId': 'Joanna',
        'Engine': 'long-form',
        'LanguageCode': 'en-GB',
    }
    mock_stream = BytesIO(b"fake audio data")
    response = {
        'RequestCharacters': len(test_text),
        'AudioStream': mock_stream,
    }
    stubber.add_response('synthesize_speech', response, expected_params)

    tts_client = tts.TextToSpeech(
        polly_client=polly_client,
        voice='Joanna',
        engine='long-form',
        language_code='en-GB',
    )
    stream = tts_client.convert_to_speech(test_text)

    assert stream.read() == b"fake audio data"
    assert tts_client.last_request_chars == len(test_text)
