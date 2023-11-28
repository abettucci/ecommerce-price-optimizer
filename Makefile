install:
	pip install --upgrade pip &&\
		pip install -r data_producer/requirements.txt	

format:
	black data_producer/*.py

lint:
	pylint --disable=R,C data_producer/*.py

all: install lint format
