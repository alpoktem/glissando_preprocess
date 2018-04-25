# -*- coding: utf-8 -*-
import os
import io
from os.path import join
import sys
from optparse import OptionParser
from pydub import AudioSegment
from proscript.proscript import Word, Proscript, Segment
from proscript.utilities import utils
import xml.etree.ElementTree as ET
import re
from praatio import tgio
from shutil import copyfile

MAX_SEGMENT_LENGTH = 30.0 #SECONDS
MFA_ALIGN_BINARY = "/Users/alp/extSW/montreal-forced-aligner/bin/mfa_align"
MFA_LEXICON = "/Users/alp/extSW/montreal-forced-aligner/pretrained_models/spanish.dict"
MFA_LM = "/Users/alp/extSW/montreal-forced-aligner/pretrained_models/spanish.zip"

def splitAudioFile(file_in_audio, speaker_ids, file_output_dir, file_prefix=""):
	audio_stereo = AudioSegment.from_file(file_in_audio, format="wav")
	[audio_leftChannel, audio_rightChannel] = audio_stereo.split_to_mono()

	spk1_audio_file = os.path.join(file_output_dir, "%s-%s.wav"%(file_prefix, speaker_ids[0]))
	spk2_audio_file = os.path.join(file_output_dir, "%s-%s.wav"%(file_prefix, speaker_ids[1]))
	audio_leftChannel.export(spk1_audio_file, format="wav")
	audio_rightChannel.export(spk2_audio_file, format="wav")

	return True

def checkFile(filename, variable, exit_if_fail=False):
	if not filename:
		print("%s file not given"%variable)
		if exit_if_fail:
			sys.exit()
	else:
		if not os.path.isfile(filename):
			print("%s file does not exist"%(filename))
			if exit_if_fail:
				sys.exit()
	return True

def to_proscript(file_in_audio, file_in_xml):
	audio_stereo = AudioSegment.from_file(file_in_audio, format="wav")
	try:
		tree = ET.parse(file_in_xml)
	except:
		print("Cannot read %s"%file_in_xml)
		sys.exit()
	root = tree.getroot()

	speaker_ids = []
	for person in root[0][1][0].findall('person'):
		speaker_ids.append(person.find('persName').text.strip())

	proscript = Proscript()
	proscript.speaker_ids = speaker_ids
	proscript.duration = audio_stereo.duration_seconds

	#parse XML
	segment_count = 0
	first_utterance = True
	for index, utterance in enumerate(root[0][1].findall('u')):
		speaker_id = utterance.attrib['who'][1:]
		start_time = float(utterance.attrib['start'])
		end_time = float(utterance.attrib['end'])

		transcript_frags = [utterance.text]
		for v in list(utterance):
			if v.tag == "vocal":
				if not v.get("type") == "non-ling":
					transcript_frags.append(v.findtext("desc"))
			elif v.tag == "del" or v.tag == "sic" or v.tag == "shift" or v.tag == "foreign":
				transcript_frags.append(v.text)
			elif not v.tag == "anchor" and not v.tag == "unclear":
				print("TAG'E BAK? %s in %s"%(v.tag, file_in_xml))
			transcript_frags.append(v.tail)

		transcript = " ".join(t.strip() for t in transcript_frags if t is not None)
		#print("xml seg:%s"%transcript)

		if not transcript.isspace():
			if first_utterance:
				curr_seg = Segment()
				curr_seg.start_time = start_time
				curr_seg.speaker_id = speaker_id
				curr_seg.end_time = end_time
				curr_seg.transcript += transcript
				first_utterance = False
			elif not curr_seg.get_value("speaker_id") == speaker_id or curr_seg.get_duration() >= MAX_SEGMENT_LENGTH:	#speaker change OR curr_seg duration is more than 30 seconds
				if curr_seg.transcript and not curr_seg.transcript.isspace():
					segment_count += 1
					curr_seg.id = segment_count
					curr_seg.transcript = normalize_transcript(curr_seg.transcript)
					proscript.add_segment(curr_seg)
					#curr_seg.to_string()
					#print("----====----")
				curr_seg = Segment()
				curr_seg.start_time = start_time
				curr_seg.speaker_id = speaker_id
				curr_seg.end_time = end_time
				curr_seg.transcript += transcript
				#print("curr_seg:%s"%curr_seg.transcript)
			else: 
				curr_seg.end_time = float(utterance.attrib['end'])
				curr_seg.transcript += ' ' + transcript
				#print("curr_seg:%s"%curr_seg.transcript)

		if index == len(root[0][1].findall('u')) - 1:
			if curr_seg.transcript and not curr_seg.transcript.isspace():
				segment_count += 1
				curr_seg.id = segment_count
				curr_seg.transcript = normalize_transcript(transcript)
				proscript.add_segment(curr_seg)
				#curr_seg.to_string()
				#print("----====----")
		
	return proscript, speaker_ids

def normalize_transcript(transcript):
	#normalize text stuff
	#remove parantheses
	transcript = re.sub('[()]', '', transcript)
	transcript = re.sub('\[.+\]', '', transcript)
	transcript = transcript.strip()

	#resolve dangling punctuation
	transcript = re.sub(r'¿ ', r'¿', transcript)
	transcript = re.sub(r' \?', r'?', transcript)
	transcript = re.sub(r'¡ ', r'¡', transcript)
	transcript = re.sub(r' !', r'!', transcript)
	transcript = re.sub(r' \. ', r'. ', transcript)
	transcript = re.sub(r' \.$', r'.', transcript)
	transcript = re.sub(r' \,$', r',', transcript)
	transcript = re.sub(r' , ', r', ', transcript)
	transcript = re.sub(r' \.\.\. ', r'... ', transcript)
	transcript = re.sub(r' \.\.\.$', r'...', transcript)

	#remove non-word elements
	transcript = re.sub(r'\s[^\w|\s]+\s', '', transcript)

	#remove repeating whitespaces
	transcript = re.sub(' +',' ', transcript)

	return transcript

def main(options):
	checkFile(options.list_of_files, "file list", exit_if_fail=True)

	if not os.path.exists(options.output_dir):
		os.makedirs(options.output_dir)

	proscript_list = []

	with open(options.list_of_files) as f:
		for line in f:
			file_id = line.split('\t')[0]
			file_in_audio = line.split('\t')[1].strip()
			file_in_xml = line.split('\t')[2].strip()
			file_output_dir = os.path.join(options.output_dir, file_id)

			if checkFile(file_in_audio, file_in_audio) and checkFile(file_in_xml, file_in_xml):
				if not os.path.exists(file_output_dir):
					os.makedirs(file_output_dir)

				proscript, speaker_ids = to_proscript(file_in_audio, file_in_xml)   
				proscript.id = file_id
				proscript.audio_file = copyfile(file_in_audio, os.path.join(file_output_dir, "%s.wav"%proscript.id))
				
				for speaker_id in proscript.speaker_ids:
					proscript.speaker_textgrid_files.append(os.path.join(file_output_dir, "%s-%s.TextGrid"%(file_id, speaker_id)))

				proscript_list.append(proscript)

				splitAudioFile(file_in_audio, speaker_ids, file_output_dir, file_id)
				utils.proscript_segments_to_textgrid(proscript, file_output_dir, file_id, speaker_segmented=True)
	
	utils.mfa_word_align(options.output_dir, mfa_align_binary=MFA_ALIGN_BINARY, lexicon=MFA_LEXICON, language_model=MFA_LM)

	#parse textgrids to get word and punctuation information. Output each to csv file	
	for proscript in proscript_list:
		utils.get_word_alignment_from_textgrid(proscript, word_tier_no=1)
		utils.assign_word_ids(proscript)

		file_output_dir = os.path.join(options.output_dir, proscript.id)
		utils.assign_acoustic_feats(proscript, file_output_dir)

		proscript_file = os.path.join(file_output_dir, "%s_proscript.csv"%proscript.id)
		proscript.to_csv(proscript_file, word_feature_set=['id', 'start_time', 'end_time', 'pause_before', 'punctuation_before', 'punctuation_after', 'f0_mean', 'f0_range', 'i0_mean', 'i0_range'], delimiter='|')

if __name__ == "__main__":
	usage = "usage: %prog [-s infile] [option]"
	parser = OptionParser(usage=usage)
	parser.add_option("-i", "--filelist", dest="list_of_files", default=None, help="list of files to process. (each line with id, wav, xml)", type="string")	#glissando files
	parser.add_option("-o", "--out_dir", dest="output_dir", default=None, help="output directory to put segmented audio and textgrids", type="string")

	(options, args) = parser.parse_args()
	main(options)