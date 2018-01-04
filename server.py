#!flask/bin/python
import sys
import os
import scipy.io.wavfile
from flask import Flask
from flask import request
from flask import jsonify
import base64
import jsonschema
import json
import time
sys.path.append("./api")
import Vokaturi


app = Flask(__name__)
errors = {
    'RequestError': {
        'message': "invalid request input",
        'status': 400,
    },
	'InternalServerError': {
        'message': "Internal Server Error",
        'status': 500,
    },
}

with open('schema.json', 'r') as f:
	schema_data = f.read()
schema = json.loads(schema_data)

@app.route('/', methods=['POST'])
def index():
	try:
	    jsonschema.validate(request.json, schema)
	except jsonschema.exceptions.ValidationError:
		return jsonify({"error":errors['RequestError']}), errors['RequestError']['status']

	record = request.json['record']
	decoded = base64.decodestring(record)
	print ("Loading library...")
	Vokaturi.load("./lib/Vokaturi_linux64.so")
	print ("Analyzed by: %s" % Vokaturi.versionAndLicense())

	print ("Reading sound file...")
	ts = time.time()
	f = open('./tmp/'+str(ts)+'.wav', 'wb')
	f.write(decoded)
	f.close()
	(sample_rate, samples) = scipy.io.wavfile.read("./tmp/"+str(ts)+".wav")
	os.remove(f.name)
	print ("   sample rate %.3f Hz" % sample_rate)
	print ("Allocating Vokaturi sample array...")
	buffer_length = len(samples)
	print ("   %d samples, %d channels" % (buffer_length, samples.ndim))
	c_buffer = Vokaturi.SampleArrayC(buffer_length)
	if samples.ndim == 1:  # mono
		c_buffer[:] = samples[:] / 32768.0
	else:  # stereo
		c_buffer[:] = 0.5*(samples[:,0]+0.0+samples[:,1]) / 32768.0

	print ("Creating VokaturiVoice...")
	voice = Vokaturi.Voice (sample_rate, buffer_length)

	print ("Filling VokaturiVoice with samples...")
	voice.fill(buffer_length, c_buffer)

	print ("Extracting emotions from VokaturiVoice...")
	quality = Vokaturi.Quality()
	emotionProbabilities = Vokaturi.EmotionProbabilities()
	voice.extract(quality, emotionProbabilities)
	data = {}
	if quality.valid:
		data['neutral'] =  "%.3f" %emotionProbabilities.neutrality
		data['happiness'] =  "%.3f" %emotionProbabilities.happiness
		data['sadness'] = " %.3f" %emotionProbabilities.sadness
		data['anger'] =  "%.3f" %emotionProbabilities.anger
		data['fear'] =  "%.3f" %emotionProbabilities.fear
		json_data = json.dumps(data)
		return json_data
	else:
		print ("Not enough sonorancy to determine emotions")

	voice.destroy()

	return jsonify({"error":errors['InternalServerError']}), errors['InternalServerError']['status']

if __name__ == '__main__':
    app.run(debug=True)
