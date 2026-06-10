import os
import logging
import subprocess
import uuid

from Crucible.config import Config

logger = logging.getLogger(__name__)

class AudioProcessor:
    def __init__(self):
        # 支持处理的常见媒体扩展名
        self.supported_formats = ['.mp3', '.wav', '.m4a', '.flac', '.aac', '.mp4', '.mkv', '.avi', '.mov', '.webm']

    def _audio_segment(self):
        """延迟导入 pydub，给 Python 3.13+ 缺少 audioop-lts 时明确提示。"""
        try:
            from pydub import AudioSegment
            return AudioSegment
        except ModuleNotFoundError as exc:
            if exc.name in {"audioop", "pyaudioop"}:
                raise RuntimeError(
                    "当前 Python 缺少音频兼容依赖 audioop-lts。"
                    "请运行 `pip install -r requirements.txt` 或单独安装 `pip install audioop-lts` 后重启后端。"
                ) from exc
            raise

    def _yt_dlp_options(self, url: str = "", output_dir: str = "", skip_download: bool = False) -> dict:
        """构造在线媒体下载配置，补齐 Bilibili 等站点需要的浏览器请求头。"""
        headers = {
            'User-Agent': Config.YTDLP_USER_AGENT,
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        if "bilibili.com" in (url or "").lower() or "b23.tv" in (url or "").lower():
            headers.update({
                'Referer': 'https://www.bilibili.com/',
                'Origin': 'https://www.bilibili.com',
            })

        options = {
            'quiet': True,
            'no_warnings': True,
            'retries': 3,
            'fragment_retries': 3,
            'socket_timeout': 20,
            'http_headers': headers,
        }
        if skip_download:
            options['skip_download'] = True
        else:
            options['format'] = 'bestaudio/best'
            options['outtmpl'] = os.path.join(output_dir, f'downloaded_{uuid.uuid4().hex}.%(ext)s')

        cookies_file = (Config.YTDLP_COOKIES_FILE or '').strip()
        if cookies_file:
            if not os.path.exists(cookies_file):
                raise FileNotFoundError(f"YTDLP_COOKIES_FILE 指向的 cookies 文件不存在: {cookies_file}")
            options['cookiefile'] = cookies_file
        return options

    def _online_media_error_message(self, error: Exception) -> str:
        err_msg = str(error)
        lower_msg = err_msg.lower()
        if "http error 412" in lower_msg or "precondition failed" in lower_msg:
            err_msg += (
                "\n\n【Bilibili 412 处理建议】"
                "\n1. 先更新 yt-dlp：`pip install -U yt-dlp`。"
                "\n2. 如果仍失败，B站要求登录态；请从浏览器导出 cookies.txt，"
                "然后设置环境变量 `YTDLP_COOKIES_FILE=你的cookies.txt绝对路径` 后重启后端。"
                "\n3. 确认链接可在当前网络和浏览器中正常打开，且没有地区、会员或风控限制。"
            )
        if any(k in lower_msg for k in ["proxy", "127.0.0.1", "refused", "积极拒绝", "connectionerror"]):
            err_msg += "\n\n【提示】检测到代理/网络连接异常。请确认代理软件（如 Clash、V2ray 等）是否已开启并正常运行。如果已关闭代理软件，请检查系统环境变量中的 HTTP_PROXY/HTTPS_PROXY 或系统代理设置，以清除残留的代理配置。"
        return err_msg

    def check_ffmpeg(self) -> bool:
        """检查系统中是否安装并配置了 FFmpeg"""
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def extract_audio_from_video(self, video_path: str, output_path: str) -> str:
        """
        使用 FFmpeg 从本地视频文件中分离并提取 16kHz 单声道 WAV 音频
        
        Args:
            video_path: 视频路径
            output_path: 输出音频路径 (.wav)
        """
        try:
            logger.info(f"提取音频中: {video_path}")
            
            if not self.check_ffmpeg():
                logger.warning("未检测到 FFmpeg 命令行工具，尝试使用 pydub 接口进行加载解析...")
                try:
                    # pydub 尝试直读
                    AudioSegment = self._audio_segment()
                    sound = AudioSegment.from_file(video_path)
                    sound = sound.set_frame_rate(16000).set_channels(1)
                    sound.export(output_path, format='wav')
                    logger.info("使用 pydub 成功提取音频。")
                    return output_path
                except Exception as ex:
                    raise RuntimeError("系统未安装 FFmpeg 且 pydub 解析视频失败，请安装 FFmpeg 环境。") from ex

            # ffmpeg 提取音频
            command = [
                'ffmpeg', '-i', video_path,
                '-vn',                      # 禁用视频输出
                '-acodec', 'pcm_s16le',     # PCM 16-bit 编码
                '-ar', '16000',             # 16000Hz 采样率
                '-ac', '1',                 # 单声道通道数
                '-y',                       # 覆盖输出
                output_path
            ]
            result = subprocess.run(command, capture_output=True, text=True, timeout=1800)
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg 运行失败: {result.stderr}")
                
            logger.info(f"音频成功分离提取至: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"提取视频音频失败: {e}", exc_info=True)
            raise

    def convert_audio_format(self, input_path: str, output_path: str, sample_rate: int = 16000) -> str:
        """
        转换本地音频文件的采样率和格式
        
        Args:
            input_path: 原始音频路径
            output_path: 转换后的 WAV 路径
            sample_rate: 采样率 (默认 16kHz)
        """
        try:
            logger.info(f"转换音频格式中: {input_path}")
            AudioSegment = self._audio_segment()
            sound = AudioSegment.from_file(input_path)
            sound = sound.set_frame_rate(sample_rate).set_channels(1)
            sound.export(output_path, format='wav')
            return output_path
        except Exception as e:
            logger.error(f"音频格式转换失败: {e}", exc_info=True)
            raise

    def process_media(self, media_path_or_url: str, temp_dir: str) -> str:
        """
        统一媒体入口，支持本地音视频处理或在线 URL (Youtube/Bilibili 等) 的下载与音频提取
        
        Args:
            media_path_or_url: 本地文件路径或网络 URL
            temp_dir: 临时工作目录
        """
        try:
            # 1. 检查是否为网络 URL
            if media_path_or_url.startswith(('http://', 'https://')):
                logger.info(f"检测到在线 URL: {media_path_or_url}，启动 yt-dlp 下载...")
                downloaded_file = self.download_online_media(media_path_or_url, temp_dir)
                media_path = downloaded_file
            else:
                media_path = media_path_or_url
                
            if not os.path.exists(media_path):
                raise FileNotFoundError(f"媒体文件不存在: {media_path}")
                
            ext = os.path.splitext(media_path)[1].lower()
            output_audio = os.path.join(temp_dir, 'processed_audio.wav')
            
            # 2. 如果是视频，进行音频分离；如果是音频，重采样
            if ext in ['.mp4', '.mkv', '.avi', '.mov', '.webm']:
                return self.extract_audio_from_video(media_path, output_audio)
            else:
                return self.convert_audio_format(media_path, output_audio)
                
        except Exception as e:
            logger.error(f"媒体预处理阶段失败: {e}")
            raise

    def download_online_media(self, url: str, output_dir: str) -> str:
        """
        使用 yt-dlp 下载网络音视频，并返回本地保存文件路径
        
        Args:
            url: 在线视频链接
            output_dir: 保存目录
        """
        try:
            import yt_dlp
            ydl_opts = self._yt_dlp_options(url, output_dir=output_dir)
            
            logger.info("开始请求网络媒体数据...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
            logger.info(f"网络媒体下载完成: {filename}")
            return filename
        except ImportError:
            raise ImportError("未发现 'yt_dlp' 第三方库，请先安装该依赖项再进行网络下载。")
        except Exception as e:
            logger.error(f"在线 URL 下载失败: {e}", exc_info=True)
            err_msg = self._online_media_error_message(e)
            raise RuntimeError(f"在线媒体下载失败: {err_msg}")

    def get_audio_duration(self, audio_path: str) -> float:
        """获取音频文件的总时长（秒）"""
        try:
            AudioSegment = self._audio_segment()
            sound = AudioSegment.from_file(audio_path)
            return sound.duration_seconds
        except Exception as e:
            logger.error(f"获取音频时长失败: {audio_path}, {e}")
            return 0.0

    def get_video_title(self, url: str) -> str:
        """使用 yt-dlp 获取在线视频的标题（不下载视频）"""
        try:
            import yt_dlp
            import re
            ydl_opts = self._yt_dlp_options(url, skip_download=True)
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get('title')
                if title:
                    # 移除非法文件名字符，方便后续可能的文件命名
                    return re.sub(r'[\\/*?:"<>|]', '_', title).strip()
        except Exception as e:
            logger.warning(f"获取视频标题失败: {url}, 错误: {e}")
        # 回退处理：截取 URL 尾部或返回安全字符串
        return url.split('/')[-1] or "Online_Video"

# 单例模式
audio_processor = AudioProcessor()
