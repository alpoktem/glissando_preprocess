# glissando_preprocess

Processes Glissando corpus TextGrids and audio files to make them inputtable to Proscripter.

## Required Libraries
- Python with libraries:
	- proscript (https://github.com/alpoktem/proscript)
	- pydub
	- praatio
	- numpy
- R with libraries:
	- plyr
	- data.table
	- geometry
	- magic
	- abind
	- mFilter 
	- polynom
	- orthopolynom
- Praat

## Run 
Before running, make sure `extract-prosodic-feats.sh` file under `dist-packages/proscript/utilities/laic` has execution permissions for all

To run:
`python process_glissando.py -i sample_file_list.txt -o sample_out`









