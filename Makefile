install:
	pip install --upgrade pip &&\
		pip install -r requirements.txt

test:
	#python -m pytest -vv test_hello.py

format:
	black *.py

lint:
	#pylint --disable=R,C hello.py

run:
	python app.py

run_local:
	CONFIG_ENV=local python app.py

all: #install lint test