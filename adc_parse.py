'''
## Чтение и проверка данных АЦП с SD карты
'''
from crccheck.crc import Crc32Mpeg2
from datetime import datetime
import fattime

# Настройки программы
ADC_SAMPLE_NUMBER = 2048 # Кол-во отсчетов АЦП в двухсекундном интервале
ADC_FRAME_START = 0 # Начальный фрейм для анализа данных (можно начинать анализ с середины файла)
ADC_FRAME_NUMBER = 1800 # Кол-во двухсекундных фреймов (интервалов) в одном файле данных
ADC_DATA_WIDTH = 4 # Разрядность данных АЦП
CHECK_CRC = True # Выполнять проверку CRC каждого фрейма или нет (существенно влияет на время выполнения программы)
CHECK_TIME = True # Выполнять проверку временных меток каждого фрейма или нет

elapsedTime = 0

all_data_int = [
	[], [], []
]

date_time_max = {
	'sec': 58,
	'min': 59,
	'hour': 23,
}

def adc_frame_analysis_fast(input_file, channel_index):
	'''
	Brief Преобразование данных АЦП и проверка контрольной суммы \n
	Param[in] *input_file* файл для чтения данных \n
	Param[in] *channel_index* индекс канала АЦП \n
	Return Вычисленное значение CRC \n
	'''
	# Вычисление CRC по данным АЦП, с измением порядка байт
	adc_data = bytearray(input_file.read(ADC_SAMPLE_NUMBER * ADC_DATA_WIDTH))
	for sample_idx in range(0, ADC_SAMPLE_NUMBER):
		sample_data = []
		for byte_idx in range(4):
			sample_data.append(adc_data[(sample_idx * ADC_DATA_WIDTH) + (3 - byte_idx)])
		sample_value = 0
		for byte_idx in range(4):
			adc_data[(sample_idx * ADC_DATA_WIDTH) + byte_idx] =  sample_data[byte_idx]
		for byte_idx in range(3):
			sample_value = sample_value + (sample_data[byte_idx] << ((2-byte_idx) * 8))
		if sample_value >= 0x800000:
			sample_value = (0x1000000 - sample_value)*(-1)
		all_data_int[channel_index].append(sample_value)
	if True == CHECK_CRC:
		return Crc32Mpeg2.calc(adc_data)
	else:
		return 0

def check_time_sequence(time_current, time_last):
	'''
	Brief Проверка последовательности временных меток \n
	Param[in] *time_current* текущая временная метка \n
	Param[in] *time_last* прошлая временная метка \n
	Return Статус ошибки \n
	'''
	min_decrement = False
	sequence_error = False
	last_frame_time_calc = {
		'sec': 0,
		'min': 0,
	}

	if (0 == time_current['sec']):
		last_frame_time_calc['sec'] = date_time_max['sec']
		min_decrement = True
	else:
		last_frame_time_calc['sec'] = time_current['sec'] - 2
	if True == min_decrement:
		if (0 == time_current['min']):
			last_frame_time_calc['min'] = date_time_max['min']
		else:
			last_frame_time_calc['min'] = time_current['min'] - 1
	else:
		last_frame_time_calc['min'] = time_current['min']
	if (last_frame_time_calc['sec'] != time_last['sec']) or \
		(last_frame_time_calc['min'] != time_last['min']):
		sequence_error = True
	return sequence_error

def main(adc_frame_start, adc_frame_count):
	''' #MAIN \n
	Brief  Чтение бинарных данных АЦП всех каналов измерения за один час \n
	Param[in] *adc_frame_start* номер фрейма данных, с которого начинается чтение \n
	Param[in] *adc_frame_count* количество фреймов данных, которые нужно прочитать \n
	Return [[], [], []] Список данных АЦП для каждого из каналов, макс. 2048*1800 чисел для одного канала \n
	Return *elapsedTime* Значения затраченного времени
	> Диапазон значений отсчета АЦП: {-2^23...+2^23-1} \n
	'''
	ADC_FILENAMES = ['CH0.DAT', 'CH1.DAT', 'CH2.DAT']
	adc_files = []
	if adc_frame_count > ADC_FRAME_NUMBER:
		adc_frame_count = ADC_FRAME_NUMBER
	start_datetime = datetime.now()
	# Открыть бинарный файл для чтения
	for file_idx in range(3):
		adc_files.append(open(ADC_FILENAMES[file_idx], 'rb'))
		
		adc_frame_descr = {
			'frame_time': [],
			'crc_calc': [],
			'crc_file': [],
		}
		crc_ok = True
		crc_err_frames = []
		time_sequence = True
		time_sequence_err_frames = []
		# Если нужно читать данные не сначала
		if 	adc_frame_start > 0:
			adc_files[file_idx].seek((4 + ADC_SAMPLE_NUMBER * ADC_DATA_WIDTH + 4) * adc_frame_start)
		for frame_idx in range(adc_frame_count):
			adc_frame_descr['frame_time'].append( fattime.convert_from_fattime(adc_files[file_idx].read(4)) )
			adc_frame_descr['crc_calc'].append( adc_frame_analysis_fast(adc_files[file_idx], file_idx) )
			adc_frame_descr['crc_file'].append( int.from_bytes(adc_files[file_idx].read(4), byteorder = 'little', signed = False) )
			if (adc_frame_descr['crc_calc'][frame_idx] != adc_frame_descr['crc_file'][frame_idx]):
				if True == CHECK_CRC:
					crc_ok = False
					crc_err_frames.append(frame_idx)
				else:
					crc_ok = 'Not tested'
			# Проверка последовательности временных меток
			if True == CHECK_TIME:
				if (frame_idx > 0) and (True == check_time_sequence(adc_frame_descr['frame_time'][frame_idx], adc_frame_descr['frame_time'][frame_idx - 1])):
					time_sequence = False
					time_sequence_err_frames.append(frame_idx)
			else:
				time_sequence = 'Not tested'

		print('Channel = ', file_idx, ':: crc_ok = ', crc_ok, ':: time_sequence = ', time_sequence)
		print('crc_err idx: ', crc_err_frames, ':: time_err idx: ', time_sequence_err_frames)
		adc_files[file_idx].close()
	
	finish_datetime = datetime.now()
	elapsedTime = finish_datetime - start_datetime
	print('>__ Data analysis time is ' + str(finish_datetime - start_datetime))
	return all_data_int, elapsedTime


if __name__ == '__main__':
	main(ADC_FRAME_START, ADC_FRAME_NUMBER)