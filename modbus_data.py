'''
## Преобразование данных устройства из набора регистров ModBus в объекты
'''
import math
import numpy as np

FFTS_FIFO_SIZE = 12                # Максимальное кол-во фреймов данных частотного анализа в FIFO

ADC_SAMPLE_NUMBER = 2048 # Кол-во отсчетов АЦП в двухсекундном интервале
ADC_RESOLUTION = 2**23 # [bits], half of the range, positive values
ADC_RANGE = 10000 # [mV]
ADC_SCALE = ADC_RANGE / ADC_RESOLUTION

ch_list = ['ch1', 'ch2', 'ch3']

def parse_diag(request_diag):
	'''
	Brief Разбор данных диагностики, полученных по ModBus \n
	Param[in] *request_diag* набор регистров с данными дагностики \n
	Return Объект с вычисленными данными диагностики и битами статуса \n
	'''
	diag_regs = {}
	diag_regs['status'] = request_diag.registers[int(0)]
	diag_regs['time'] = request_diag.registers[int(2)] + (request_diag.registers[int(3)] << 16)
	diag_regs['hum_int'] = request_diag.registers[int(4)] / 10
	diag_regs['temp_int'] = request_diag.registers[int(5)] / 10
	diag_regs['hum_ext'] = request_diag.registers[int(6)] / 10
	diag_regs['temp_ext'] = request_diag.registers[int(7)] / 10
	diag_regs['inp_vlt'] = request_diag.registers[int(8)] / 1000
	diag_regs['sd_total'] = request_diag.registers[int(9)] / 16
	diag_regs['sd_free'] = request_diag.registers[int(10)] / 16
	diag_regs['fifo_wr'] = request_diag.registers[int(11)] & 0x00FF
	diag_regs['fifo_rd'] = (request_diag.registers[int(11)] & 0xFF00) >> 8
	# Вычислим кол-во фреймов данных в FIFO
	if diag_regs['fifo_wr'] == diag_regs['fifo_rd']:
		diag_regs['fifo_level'] = 0
	elif diag_regs['fifo_wr'] > diag_regs['fifo_rd']:
		diag_regs['fifo_level'] = diag_regs['fifo_wr'] - diag_regs['fifo_rd']
	else:
		diag_regs['fifo_level'] = diag_regs['fifo_wr'] + FFTS_FIFO_SIZE - diag_regs['fifo_rd']
	diag_regs['version'] = 'v{0}.{1}.{2}'.format( ((request_diag.registers[int(12)] & 0xF000) >> 12),
		((request_diag.registers[int(12)] & 0x0FF0) >> 4), ((request_diag.registers[int(12)] & 0x000F) >> 0))
	
	diag_status = {
		'sync': 0 if 0 == (diag_regs['status'] & 0x0001) else 1,
		'pwr_ok': 0 if 0 == (diag_regs['status'] & 0x0002) else 1,
		'sd_ok': 0 if 0 == (diag_regs['status'] & 0x0004) else 1,
		'rtc_ok': 0 if 0 == (diag_regs['status'] & 0x0008) else 1,
		'env_int': 0 if 0 == (diag_regs['status'] & 0x0010) else 1,
		'env_ext': 0 if 0 == (diag_regs['status'] & 0x0020) else 1,
		'time_error': 0 if 0 == (diag_regs['status'] & 0x0040) else 1,
		'sync_error': 0 if 0 == (diag_regs['status'] & 0x0080) else 1,
		'fifo_over': 0 if 0 == (diag_regs['status'] & 0x0100) else 1,
		'fifo_under': 0 if 0 == (diag_regs['status'] & 0x0200) else 1,
		'sd_full': 0 if 0 == (diag_regs['status'] & 0x0400) else 1,
		'sd_ffts_reading': 0 if 0 == (diag_regs['status'] & 0x0800) else 1,
		'sd_adc_reading': 0 if 0 == (diag_regs['status'] & 0x1000) else 1,
		'sd_ffts_success': 0 if 0 == (diag_regs['status'] & 0x2000) else 1,
		'sd_adc_success': 0 if 0 == (diag_regs['status'] & 0x4000) else 1,
		'sd_req_error': 0 if 0 == (diag_regs['status'] & 0x8000) else 1,
	}
	
	return {'regs': diag_regs, 'status': diag_status}

def parse_ffts(ffts_regs):
	'''
	Brief Разбор данных частотного анализа \n
	Param[in] *ffts_regs* набор регистров с данными частотного анализа \n
	Return Объект с данными частотного анализа \n
	'''
	FREQ_BLOCK_REG_COUNT = 96  # Кол-во анализируемых гармоник
	TIME_REG_COUNT = 2         # Кол-во регистров времени
	CH_REG_COUNT = FREQ_BLOCK_REG_COUNT * 4 + TIME_REG_COUNT  # Полное кол-во регистров частотного анализа для одного канала

	# Создадим объект для хранения полученных данных частотного анализа
	freq_data = {
		'ch1': {
			'harm_rms': [],	'harm_max': [], 'time' : 0, },
		'ch2': {
			'harm_rms': [],	'harm_max': [],	'time' : 0, },
		'ch3': {
			'harm_rms': [],	'harm_max': [],	'time' : 0, },
	}

	for ch_idx in range(3):
		ch_name = ch_list[ch_idx]
		for block_idx in range(4):
			for harm_idx in range(int(FREQ_BLOCK_REG_COUNT / 2)):
				real_bytes = []
				real_bytes.append( (ffts_regs[ch_name][block_idx].registers[(harm_idx * 2) + 0] & 0x00FF) >> 0 )
				real_bytes.append( (ffts_regs[ch_name][block_idx].registers[(harm_idx * 2) + 0] & 0xFF00) >> 8 )
				real_bytes.append( (ffts_regs[ch_name][block_idx].registers[(harm_idx * 2) + 1] & 0x00FF) >> 0 )
				real_bytes.append( (ffts_regs[ch_name][block_idx].registers[(harm_idx * 2) + 1] & 0xFF00) >> 8 )
				real_bytes_np = np.array(real_bytes, dtype=np.uint8)
				real_as_float = real_bytes_np.view(dtype=np.float32)
				if block_idx < 2:
					# Вычисление физического значения RMS гармоники, нормализация по длине массива
					harm_rms = (real_as_float[0] / ADC_SAMPLE_NUMBER) * ADC_SCALE
					# Умножим амплитуду на 2 с учетом энергии комплексной составляющей для всех частот кроме нулевой, и вычислим RMS как *sqrt(2)/2
					if not (0 == block_idx and 0 == harm_idx):
						harm_rms = harm_rms * 2 * (math.sqrt(2) / 2)
					freq_data[ch_name]['harm_rms'].append(harm_rms)
				elif block_idx < 4:
					# Вычисление физического значения амплитуды гармоники, нормализация по длине массива
					max_ampl = (real_as_float[0] / ADC_SAMPLE_NUMBER) * ADC_SCALE
					# Умножим амплитуду на 2 с учетом энергии комплексной составляющей для всех частот кроме нулевой
					if not (2 == block_idx and 0 == harm_idx):
						max_ampl = max_ampl * 2
					freq_data[ch_name]['harm_max'].append(max_ampl)
		freq_data[ch_name]['time'] = ffts_regs['time']
	return freq_data

def parse_adc(adc_data_regs, time_stamp):
	'''
	Brief  Разбор бинарных данных АЦП, прочитанных с карты памяти SD \n
	Param[in] *adc_data_regs* набор регистров с данными АЦП (100 блоков по 123 16-битных регистра) \n
	Param[in] *time_stamp* временная метка \n
	Return Объект с данными АЦП \n
	'''
	BLOCK_SIZE = 123
	BLOCK_COUNT = 100
	# Упакуем данные в 32-разрядные слова
	REG_COUNT = BLOCK_SIZE * BLOCK_COUNT
	WORD_COUNT = int(REG_COUNT / 2)
	adc_data_words = []	
	for word_idx in range(WORD_COUNT):
		word_value = adc_data_regs[word_idx * 2 + 0] + (adc_data_regs[word_idx * 2 + 1] << 16)
		adc_data_words.append(word_value)
	# Упакуем данные в объект
	WORDS_PER_CHANNEL = int(WORD_COUNT / 3)

	adc_data = {
		'ch1': {
			'timestamp': 0, 'data': [], 'crc': False, },
		'ch2': {
			'timestamp': 0, 'data': [], 'crc': False, },
		'ch3': {
			'timestamp': 0, 'data': [], 'crc': False, },
	}
	for ch_idx in range(3):
		adc_data[ch_list[ch_idx]]['timestamp'] = adc_data_words[0 + (ch_idx * WORDS_PER_CHANNEL)]
		for word_idx in range(1, WORDS_PER_CHANNEL - 1):
			word_value = adc_data_words[word_idx + (ch_idx * WORDS_PER_CHANNEL)]
			word_value = word_value >> 8
			if word_value >= 0x800000:
				word_value = (0x1000000 - word_value)*(-1)
			# Преобразование в физическую величину и запись в объект
			adc_data[ch_list[ch_idx]]['data'].append(word_value * ADC_SCALE)
		adc_data[ch_list[ch_idx]]['crc'] = adc_data_words[word_idx + 1 + (ch_idx * WORDS_PER_CHANNEL)]
	adc_data['service'] = {}
	adc_data['service']['timestamp'] = time_stamp
	return adc_data