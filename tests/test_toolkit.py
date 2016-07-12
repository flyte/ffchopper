import os
from decimal import Decimal

import mock
import pytest
import magic

import avtoolkit
from avtoolkit.util import tempdir


TEST_VID_PATH = "tests/test.mp4"
TEST_IMG_PATH = "tests/tux.png"


class EarlyExitException(Exception):
    """
    Exception used to exit a function when a Mock with this exception as a side effect is hit.
    """
    pass


@mock.patch("avtoolkit.video.check_output")
def test_ffprobe_calls_check_output(mock_check_output):
    """
    Should call check_output with the ffprobe binary and supplied arguments.
    """
    args = ["a", "b", "c"]
    avtoolkit.video.ffprobe(args)
    assert mock_check_output.called
    assert mock_check_output.call_args[0][0] == [avtoolkit.video.FFPROBE_BIN]+args


@mock.patch("avtoolkit.video.check_output", return_value=b"Hi!")
def test_ffmpeg_calls_check_output(mock_check_output):
    """
    Should call check_output with the ffmpeg binary and supplied arguments when
    capture_stdout is True.
    """
    args = ["a", "b", "c"]
    ret = avtoolkit.video.ffmpeg(args, capture_stdout=True)
    assert mock_check_output.called
    assert mock_check_output.call_args[0][0] == [avtoolkit.video.FFMPEG_BIN]+args
    assert ret == "Hi!"


@mock.patch("avtoolkit.video.check_call")
def test_ffmpeg_calls_check_call(mock_check_call):
    """
    Should call check_call with the ffmpeg binary and supplied carguments when
    capture_stdout is False.
    """
    args = ["a", "b", "c"]
    avtoolkit.video.ffmpeg(args, capture_stdout=False)
    assert mock_check_call.called
    assert mock_check_call.call_args[0][0] == [avtoolkit.video.FFMPEG_BIN]+args


class TestUtil:
    def test_tempdir(self):
        """
        Should create a temporary directory and remove it afterwards.
        """
        @tempdir
        def test(tmpdir):
            assert os.path.exists(tmpdir)
            return tmpdir
        tmpdir = test()
        assert not os.path.exists(tmpdir)


class TestVideo:
    def test_video_exists(self):
        """
        Should raise a ValueError if a file does not exist at the path specified.
        """
        with pytest.raises(IOError):
            avtoolkit.Video("a_non_existent_file.none")

    @mock.patch("avtoolkit.video.ffprobe", return_value="{}")
    def test_data_calls_ffprobe(self, mock_ffprobe):
        """
        Should call ffprobe on the first 'get' of the `data` property and not
        on subsequent ones.
        """
        vid = avtoolkit.Video(TEST_VID_PATH)
        assert not mock_ffprobe.called
        vid.data
        assert mock_ffprobe.called
        assert mock_ffprobe.call_count == 1
        vid.data
        assert mock_ffprobe.call_count == 1

    def test_data_returns_dict(self):
        """
        Should return a dictionary containing information about the video.
        """
        vid = avtoolkit.Video(TEST_VID_PATH)
        assert vid.data
        assert isinstance(vid.data, dict)

    def test_data_contains_streams(self):
        """
        Should return a dict containing the "streams" key.
        """
        vid = avtoolkit.Video(TEST_VID_PATH)
        assert "streams" in vid.data

    @tempdir
    def test_extract_audio(tempdir, self):
        """
        Should extract the audio from a video and save it to the specified path.
        """
        vid = avtoolkit.Video(TEST_VID_PATH)
        audio_file = os.path.join(tempdir, "audio.aac")
        vid.extract_audio(audio_file)
        assert os.path.exists(audio_file)
        assert magic.from_file(audio_file, mime=True) == "audio/x-hx-aac-adts"

    @pytest.mark.slow
    @tempdir
    def test_to_images(tempdir, self):
        """
        Should split the video into a sequence of images.
        """
        vid = avtoolkit.Video(TEST_VID_PATH)
        frame_count = int(vid.data["streams"][0]["nb_frames"])
        vid.to_images(tempdir, "jpg")
        files = os.listdir(tempdir)
        assert len(files) == frame_count
        assert magic.from_file(os.path.join(tempdir, files[0]), mime=True) == "image/jpeg"

    @pytest.mark.slow
    @tempdir
    def test_from_images(tempdir, self):
        """
        Should build a video from a sequence of images and return it as a Video.
        """
        output_file = os.path.join(tempdir, "output.mp4")
        avtoolkit.Video.from_images("tests/images/test-%03d.jpg", 25, output_file)
        assert os.path.exists(output_file)
        assert magic.from_file(output_file, mime=True) == "video/mp4"

    @pytest.mark.slow
    @tempdir
    def test_overlay(tempdir, self):
        """
        Should overlay a video on top of a section of the original video.
        """
        vid = avtoolkit.Video(TEST_VID_PATH)
        vid2 = avtoolkit.Video(TEST_VID_PATH)
        output_path = os.path.join(tempdir, "joined.mp4")
        vid.overlay(vid2, 1, output_path)
        assert os.path.exists(output_path)
        assert magic.from_file(output_path, mime=True) == "video/mp4"

    @pytest.mark.slow
    @tempdir
    def test_overlay_with_image(tempdir, self):
        """
        Should overlay an image on top of a section of the original video.
        """
        vid = avtoolkit.Video(TEST_VID_PATH)
        img = avtoolkit.Video(TEST_IMG_PATH)
        output_path = os.path.join(tempdir, "output.mp4")

        # Should raise an AttributeError if `overlay_duration` is not provided with an image.
        with pytest.raises(AttributeError):
            vid.overlay(img, 2, output_path)

        vid.overlay(img, 2, output_path, overlay_duration=2)
        assert os.path.exists(output_path)
        assert magic.from_file(output_path, mime=True) == "video/mp4"

    @pytest.mark.slow
    @tempdir
    def test_reencode(tempdir, self):
        """
        Should convert the video to the desired encoding based on the file extension.
        """
        assert magic.from_file(TEST_VID_PATH, mime=True) == "video/mp4"
        vid = avtoolkit.Video(TEST_VID_PATH)
        output_file = os.path.join(tempdir, "output.avi")
        vid.reencode(output_file)
        assert magic.from_file(output_file, mime=True) == "video/x-msvideo"

    @pytest.mark.slow
    @tempdir
    def test_split(tempdir, self):
        """
        Should split a video at a given second and return two Videos.
        """
        a = os.path.join(tempdir, "a.mp4")
        b = os.path.join(tempdir, "b.mp4")
        vid = avtoolkit.Video(TEST_VID_PATH)
        original_length = Decimal(vid.data["streams"][0]["duration"])
        split_seconds = Decimal("2.52")

        result = vid.split(split_seconds, a, b)
        assert isinstance(result, tuple)
        vid_a, vid_b = result
        for output in (a, b):
            assert os.path.exists(output)
            assert magic.from_file(output, mime=True) == "video/mp4"
        assert Decimal(vid_a.data["streams"][0]["duration"]) == split_seconds
        assert Decimal(vid_b.data["streams"][0]["duration"]) == original_length - split_seconds

    @pytest.mark.slow
    @tempdir
    def test_concatenate(tempdir, self):
        pass

    def test_insert(self):
        """
        TODO
        """
        vid = avtoolkit.Video(TEST_VID_PATH)
        vid.insert(vid, 1)