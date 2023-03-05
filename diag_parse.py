'''
## Чтение и проверка данных диагностики с SD карты
'''
import os, io, shutil, json, array, zlib, fattime
from crccheck.crc import Crc32Mpeg2
from datetime import datetime

DIAGNOSTICS_DATA_COUNT = 13
ADC_FRAME_COUNT = 1800
DIAG_DATA_WIDTH = 4
VOLTAGE_POINTS_COUNT = 20
CHECK_CRC = True

date_time_max = {
	'sec': 58,
	'min': 59,
	'hour': 23,
}

def diag_frame_analysis_fast(input_file):
	'''
	Brief Преобразование данных диагностики и проверка контрольной суммы \n
	Param[in] *input_file* файл для чтения данных \n
	Return Вычисленное значение CRC \n
	'''
	# Вычисление CRC по данным диагностики, с измением порядка байт
	diag_data = bytearray(input_file.read(DIAGNOSTICS_DATA_COUNT * DIAG_DATA_WIDTH))
	for sample_idx in range(0, DIAGNOSTICS_DATA_COUNT):
		sample_data = []
		for byte_idx in range(4):
			sample_data.append(diag_data[(sample_idx * DIAG_DATA_WIDTH) + (3 - byte_idx)])
		for byte_idx in range(4):
			diag_data[(sample_idx * DIAG_DATA_WIDTH) + byte_idx] =  sample_data[byte_idx]
	input_file.read(DIAG_DATA_WIDTH)
	if True == CHECK_CRC:
		return Crc32Mpeg2.calc(diag_data)
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

def main(adc_frame_count):
	''' #MAIN
	Brief Чтение данных диагностики за один час \n
	Param[in] *adc_frame_count* количество фреймов данных, которые нужно прочитать \n
	Return Словарь данных диагностики, 1800 значений каждого параметра \n
	'''
	DIAG_FILENAME = 'DIAG.DAT'
	diag_files = []
	if adc_frame_count > ADC_FRAME_COUNT:
		adc_frame_count = ADC_FRAME_COUNT
	start_datetime = datetime.now()
	# Открыть бинарный файл для чтения
	diag_files.append(open(DIAG_FILENAME, 'rb'))
	
	diag_frame_descr = {
		'frame_time': [],
		'inp_voltage': [],
		'hum_int': [],
		'temp_int': [],
		'hum_ext': [],
		'temp_ext': [],
		'crc_file': [],
		'crc_calc': [],
	}
	crc_ok = True
	crc_err_frames = []
	time_sequence = True
	time_sequence_err_frames = []
	for frame_idx in range(adc_frame_count):
		diag_frame_descr['frame_time'].append( fattime.convert_from_fattime(diag_files[0].read(4)) )
		for voltage_point_index in range (VOLTAGE_POINTS_COUNT):
			diag_frame_descr['inp_voltage'].append( int.from_bytes(diag_files[0].read(2), byteorder = 'little', signed = False) )
		diag_frame_descr['hum_int'].append( int.from_bytes(diag_files[0].read(2), byteorder = 'little', signed = False) )
		diag_frame_descr['temp_int'].append( int.from_bytes(diag_files[0].read(2), byteorder = 'little', signed = True) )
		diag_frame_descr['hum_ext'].append( int.from_bytes(diag_files[0].read(2), byteorder = 'little', signed = False) )
		diag_frame_descr['temp_ext'].append( int.from_bytes(diag_files[0].read(2), byteorder = 'little', signed = True) )
		diag_frame_descr['crc_file'].append( int.from_bytes(diag_files[0].read(4), byteorder = 'little', signed = False) )
		diag_files[0].seek(-(DIAGNOSTICS_DATA_COUNT + 1) * DIAG_DATA_WIDTH, 1)

		diag_frame_descr['crc_calc'].append( diag_frame_analysis_fast(diag_files[0]) )
		if (diag_frame_descr['crc_calc'][frame_idx] != diag_frame_descr['crc_file'][frame_idx]):
			if True == CHECK_CRC:
				crc_ok = False
				crc_err_frames.append(frame_idx)
			else:
				crc_ok = 'Not tested'''
		# Проверка последовательности временных меток
		if (frame_idx > 0) and (True == check_time_sequence(diag_frame_descr['frame_time'][frame_idx], diag_frame_descr['frame_time'][frame_idx - 1])):
			time_sequence = False
			time_sequence_err_frames.append(frame_idx)

	print('Diagnostics ', ':: crc_ok = ', crc_ok, ':: time_sequence = ', time_sequence)
	print('crc_err idx: ', crc_err_frames, ':: time_err idx: ', time_sequence_err_frames)
	diag_files[0].close()
	
	finish_datetime = datetime.now()
	print('>__ Data analysis time is ' + str(finish_datetime - start_datetime))
	return diag_frame_descr

if __name__ == '__main__':
	main(ADC_FRAME_COUNT)