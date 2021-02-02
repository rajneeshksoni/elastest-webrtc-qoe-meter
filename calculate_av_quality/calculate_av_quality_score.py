import logging
import subprocess
import os
import re
import shutil
import xml.etree.ElementTree as ET


LOGGING_PREFIX = "vmaf"
VMAF_XML_NAME = "vmaf.xml"
TEMP_DIR_PATH = "quality_temp_dir"
FFMPEG_LOG = TEMP_DIR_PATH+'/ffmpeg_log.log'
TEMP_VOL_FILE_PATH = TEMP_DIR_PATH + "/" + "vol.log"
VISQOL_LOG_PATH = TEMP_DIR_PATH + "/" + "visqol.log"
SEGMENT_PATH = TEMP_DIR_PATH + "/segment.wav"

convert_webm_to_mp4 = "ffmpeg -y -i  {web_file_path} -an -vcodec copy  {temp_file_path}/out.mp4"
convert_mp4_to_rgb = "ffmpeg -y -i  {temp_file_path}/out.mp4 -s {width}x{height} -pix_fmt rgb24  {temp_file_path}/degraded.rgb"
convert_reference_to_rgb = "ffmpeg -y -i  {reference_file_path}  -pix_fmt rgb24  {temp_file_path}/reference.rgb"
generate_reference_for_vmaf = "{dmtx_path}  -w {width}  -h {height}  -d  {temp_file_path}/degraded.rgb   -o  {temp_file_path}/reference.rgb   -V  {temp_file_path}/degraded_for_vmaf.rgb"
calculate_vmaf = "ffmpeg   -s {width}x{height}   -pix_fmt rgb24  -i   {temp_file_path}/degraded.rgb   -s {width}x{height}   -pix_fmt rgb24 \
  -i  {temp_file_path}/degraded_for_vmaf.rgb     -lavfi libvmaf=\"psnr=1:phone_model=1:log_path={vmaf_path}:model_path=/usr/local/bin/vmaf_float_v0.6.1.pkl\" -report -f null -"

av_silence_detection = "ffmpeg -i {web_file_path}  -af silencedetect=noise=-30dB:d=0.5 -f null - 2> {vol_file_path}"
wav_file_creation = "ffmpeg -y -i {web_file_path} -ar 16000 -vn  {temp_dir_path}/tmp.wav"
segment_files_creation = "ffmpeg -y -ss {start_time} -i {temp_dir_path}/tmp.wav -acodec copy -t {duration} {segment_path}"
visqol_cmd = "{visqol} --reference_file {reference_file}    --degraded_file {degraded_file}  --similarity_to_quality_model {model_path}  --use_speech_mode"


def create_directory(dir_path):
    logging.info(LOGGING_PREFIX + " create directory for transcode output " + dir_path)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)


def remove_directory(dir_path):
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)

    for f in os.listdir("./"):
        if "ffmpeg-" in f:
            os.remove(os.path.join("./", f))


class VmafUtil:
    def __init__(self, degraded_webm_file,reference_file,
                         width,height,
                         dmtx_rgb_path):
        self.webm_degraded_file = degraded_webm_file
        self.height = height
        self.width = width
        self.reference_file_path = reference_file
        self.dmtx_path = dmtx_rgb_path


    def calaculate_vmaf_score(self):

        create_directory(TEMP_DIR_PATH)
        FFLOG = open(FFMPEG_LOG, 'w')
        terminal_command = convert_webm_to_mp4.format(web_file_path=self.webm_degraded_file, temp_file_path=TEMP_DIR_PATH)
        returned_value = subprocess.call(terminal_command, shell=True,stderr=FFLOG,stdout=FFLOG)

        if returned_value != 0:
            logging.error(LOGGING_PREFIX + " error in converting webm to mp4 " + str(returned_value))
            return
        else:
            logging.info(LOGGING_PREFIX + " webm converted to mp4 ")

        terminal_command = convert_mp4_to_rgb.format(width=self.width, height=self.height, temp_file_path=TEMP_DIR_PATH)
        returned_value = subprocess.call(terminal_command, shell=True,stderr=FFLOG,stdout=FFLOG)

        if returned_value != 0:
            logging.error(LOGGING_PREFIX + " error in getting rgb file from degraded file " + str(returned_value))
            return
        else:
            logging.info(LOGGING_PREFIX + " webm to rgb for degraded file done ")

        terminal_command = convert_reference_to_rgb.format(reference_file_path=self.reference_file_path, temp_file_path=TEMP_DIR_PATH)
        returned_value = subprocess.call(terminal_command, shell=True,stderr=FFLOG,stdout=FFLOG)

        if returned_value != 0:
            logging.error(LOGGING_PREFIX + " error in third step of calculation " + str(returned_value))
            return
        else:
            logging.info(LOGGING_PREFIX + " third step completed ")

        terminal_command = generate_reference_for_vmaf.format(dmtx_path=self.dmtx_path, width=self.width, height=self.height, temp_file_path=TEMP_DIR_PATH)
        returned_value = subprocess.call(terminal_command, shell=True,stderr=FFLOG,stdout=FFLOG)

        if returned_value != 0:
            logging.error(LOGGING_PREFIX + " error in fourth step of calculation " + str(returned_value))
            return
        else:
            logging.info(LOGGING_PREFIX + " fourth step completed ")

        terminal_command = calculate_vmaf.format(width=self.width, height=self.height,vmaf_path=VMAF_XML_NAME,temp_file_path=TEMP_DIR_PATH)
        returned_value = subprocess.call(terminal_command, shell=True,stderr=FFLOG,stdout=FFLOG)

        if returned_value != 0:
            logging.error(LOGGING_PREFIX + " error in fifth step of calculation " + str(returned_value))
            return
        else:
            logging.info(LOGGING_PREFIX + " fifth step completed ")

        tree = ET.parse(VMAF_XML_NAME)
        root = tree.getroot()

        for child in root:
            if ('aggregateVMAF' in child.attrib.keys()):
                print("VMAF = " + child.attrib['aggregateVMAF'])
                print("PSNR = " + child.attrib['aggregatePSNR'])
                break

        FFLOG.close()
        remove_directory(TEMP_DIR_PATH)


class AudioScoreUtil:
    def __init__(self, degraded_webm_file, reference_file,visqol_path,visqol_model_path):
        self.degraded_file = degraded_webm_file
        self.reference_file = reference_file
        self.visqol_path = visqol_path
        self.visqol_model = visqol_model_path

    def detect_silence(self):

        create_directory(TEMP_DIR_PATH)
        FFLOG = open(FFMPEG_LOG, 'w')
        terminal_command = av_silence_detection.format(web_file_path=self.degraded_file, vol_file_path=TEMP_VOL_FILE_PATH)
        returned_value = subprocess.call(terminal_command, shell=True,stdout=FFLOG,stderr=FFLOG)
        FFLOG.close()
        if returned_value != 0:
            logging.error(LOGGING_PREFIX + " error in silence detection " + str(returned_value))
        else:
            logging.info(LOGGING_PREFIX + " silence detection successfull")
            self.get_silence_start_time(TEMP_VOL_FILE_PATH)

    def get_silence_start_time(self, output_file_path):

        with open(output_file_path, mode='r') as infile:
            content = infile.readlines()
        content = [x.strip() for x in content]

        result = []
        for i in range(len(content)):
            if 'silencedetect' not in content[i]:
                continue

            if 'silence_duration' in content[i]:
                tmp = content[i].split(" ")
                dur = float(tmp[len(tmp) - 1])
                if dur > 2:
                    result.append(float(tmp[4]))
                    # tmp = content[i-1].split(" ")
                    # result.append(float(tmp[len(tmp) - 1]))

        logging.info(f" result start time {result}")
        self.create_wav_segment(result)

    def create_wav_segment(self, silence_start_time):

        FFLOG = open(FFMPEG_LOG, 'w')
        terminal_command = wav_file_creation.format(web_file_path=self.degraded_file, temp_dir_path=TEMP_DIR_PATH)
        returned_value = subprocess.call(terminal_command, shell=True,stderr=FFLOG,stdout=FFLOG)

        if returned_value != 0:
            logging.error(LOGGING_PREFIX + " wav file error" + str(returned_value))
            return
        else:
            logging.info(LOGGING_PREFIX + " wav file created")

        index = 1

        for i in range(2, len(silence_start_time) ):
            dur = silence_start_time[i] - silence_start_time[i-1] + 1.5
            terminal_command = segment_files_creation.format(start_time=silence_start_time[i-1] - 2, temp_dir_path=TEMP_DIR_PATH, duration=dur, segment_path=SEGMENT_PATH)
            returned_value = subprocess.call(terminal_command, shell=True,stderr=FFLOG,stdout=FFLOG)
            if returned_value != 0:
                logging.error(LOGGING_PREFIX + " wav segments failure" + str(returned_value))
                return
            else:
                logging.info(LOGGING_PREFIX + " wav segments created start=" + str(silence_start_time[i-1] - 2))
            index += 1
            #calculate visqol score
            terminal_command = visqol_cmd.format(visqol=self.visqol_path,reference_file=self.reference_file,degraded_file=SEGMENT_PATH,model_path=self.visqol_model)
            f = open(VISQOL_LOG_PATH, "w")
            returned_value = subprocess.call(terminal_command, shell=True,stdout=f,stderr=f)
            if returned_value != 0:
                logging.error(LOGGING_PREFIX + " wav segments failure" + str(returned_value))
                return
            else:
                logging.info(LOGGING_PREFIX + " wav segments created")
            f.close()
            with open(VISQOL_LOG_PATH) as fp:
                line = fp.readline()
                cnt = 1
                while line:
                    if "MOS-LQO" in line:
                        score = line.replace("MOS-LQO:","")
                        score = score.strip()
                        print(" VISQOL SCORE = " + score)
                        break
                    else:
                        line = fp.readline()
                        cnt += 1
        FFLOG.close()
        remove_directory(TEMP_DIR_PATH)



if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)

    degraded_webm_file = "/Users/rajneesh.soni/tempdir/streaming_952415846336995.webm"
    width = 540
    height = 360
    reference_file = "/Users/rajneesh.soni/devMedia/elastest-webrtc-qoe-meter/interview_overlay.y4m"
    dmtx_rgb_path = "/Users/rajneesh.soni/tempdir/dmtx-utils/dmtxread/dmtxRGBread"
    audio_reference_file = "/Users/rajneesh.soni/devMedia/elastest-webrtc-qoe-meter/femmale_2sec_silence.wav"
    visqol_path = "/Users/rajneesh.soni/devMedia/visqol/bazel-bin/visqol"
    visqol_model_path = "/Users/rajneesh.soni/devMedia/visqol/model/libsvm_nu_svr_model.txt"

    vmaf_util = VmafUtil(degraded_webm_file,
                         reference_file,
                         width,
                         height,
                         dmtx_rgb_path)

    vmaf_score = vmaf_util.calaculate_vmaf_score()

    audio_util = AudioScoreUtil(degraded_webm_file,audio_reference_file,visqol_path,visqol_model_path)
    audio_util.detect_silence()


