'''
## Создание и отображение графиков частотного анализа и исходных сигналов
'''
import matplotlib.pyplot as plt
import numpy as np
import fattime, math

ONLY_POSITIVE_VALUES = True    # Конвертировать отрицательные значения амплитуд и фаз в положительные
FFT_RANGE1_START =    0        # 0..20 Hz range start
FFT_RANGE1_STOP  =   39        # 0..20 Hz range stop */
FFT_RANGE1_STEP  =    1        # 0..20 Hz range step 0.5Hz */
FFT_RANGE2_START =   40        # 20..50 Hz range start */
FFT_RANGE2_STOP  =   99        # 20..50 Hz range stop */
FFT_RANGE2_STEP  =    2        # 20..50 Hz range step 1.0Hz */
FFT_RANGE3_START =  100        # 50..100 Hz range start */
FFT_RANGE3_STOP  =  200        # 50..100 Hz range stop */
FFT_RANGE3_STEP  =    4        # 50..100 Hz range step 2Hz */
FFT_LENGTH_RANGE1 = int(((FFT_RANGE1_STOP-FFT_RANGE1_START) / FFT_RANGE1_STEP) + 1)  # 40, первый частотный диапазон */
FFT_LENGTH_RANGE2 = int(((FFT_RANGE2_STOP-FFT_RANGE2_START) / FFT_RANGE2_STEP) + 1)  # 30, второй частотный диапазон */
FFT_LENGTH_RANGE3 = int(((FFT_RANGE3_STOP-FFT_RANGE3_START) / FFT_RANGE3_STEP) + 1)  # 26, третий частотный диапазон */
FFT_LENGTH_SHORT = FFT_LENGTH_RANGE1 + FFT_LENGTH_RANGE2 + FFT_LENGTH_RANGE3         # 96, кол-во передаваемых гармоник */

ADC_SAMPLE_NUMBER = 2048 # Кол-во отсчетов АЦП в двухсекундном интервале
ADC_RESOLUTION = 2**23 # [bits], half of the range, positive values
ADC_RANGE = 10000 # [mV]
ADC_SCALE = ADC_RANGE / ADC_RESOLUTION

DISPLAY_CHANNEL_IDX = 0 # {0..2}: канал, данные которого отображаются на графике

ch_list = ['ch1', 'ch2', 'ch3']

def fft_plot(conn):
	'''
	Brief Построение графиков частотного анализа \n
	Param[in] *conn* канал передачи данных между основным и графическим процессами \n
	Return None \n
	'''
	# Установка частотного диапазона, заполнение массива частотных меток
	x = []
	frequency = 0.0
	for freq_idx in range(0, FFT_LENGTH_RANGE1):
		x.append(frequency)
		frequency = frequency + (FFT_RANGE1_STEP / 2)
	frequency = 20.0
	for freq_idx in range(0, FFT_LENGTH_RANGE2):
		x.append(frequency)
		frequency = frequency + (FFT_RANGE2_STEP / 2)
	frequency = 50.0
	for freq_idx in range(0, FFT_LENGTH_RANGE3):
		x.append(frequency)
		frequency = frequency + (FFT_RANGE3_STEP / 2)
	ready_freq_data = conn.recv()
	# Установка значений по умолчанию
	y_ampl = np.arange(0, FFT_LENGTH_SHORT, 1)
	y_phase = np.arange(0, FFT_LENGTH_SHORT, 1)
	# Настройка графиков
	fig, axes = plt.subplots(nrows=2, ncols=1)
	axes[0].set_xlabel('Частота, Гц')
	axes[0].set_ylabel('СКЗ амплитуд, мВ')
	axes[0].set_facecolor('seashell')
	axes[0].set_title('Канал {0}'.format(ch_list[DISPLAY_CHANNEL_IDX]))
	axes[1].set_xlabel('Частота, Гц')
	axes[1].set_ylabel('Макс. амплитуда, мВ')
	axes[1].set_facecolor('seashell')
	fig.set_facecolor('floralwhite')
	fig.set_figwidth(12)    #  ширина Figure
	fig.set_figheight(6)    #  высота Figure
	rects_ampl = axes[0].bar(x, y_ampl, color='DarkSlateBlue', width = 0.4)
	rects_max = axes[1].bar(x, y_phase, color='SeaGreen', width = 0.4)

	# Бесконечный цикл по отрисовке графиков
	while True:
		# Получение новых данных по каналу (Pipe), заполнение соотв. списков
		ready_freq_data = conn.recv()
		time_obj = fattime.convert_from_fattime(ready_freq_data['ch1']['time'].to_bytes(4, 'little'))
		time_str = '{0:02d}:{1:02d}:{2:02d}'.format(time_obj['hour'], time_obj['min'], time_obj['sec'])
		date_str = '{0:02d}.{1:02d}.{2:02d}'.format(time_obj['day'], time_obj['mon'], time_obj['year'])
		axes[0].set_title('Канал {0} - данные частотного анализа, '.format(ch_list[DISPLAY_CHANNEL_IDX]) + time_str + ' ' + date_str)

		y_ampl = []
		y_max = []
		for freq_idx in range(FFT_LENGTH_SHORT):
			y_ampl.append( ready_freq_data[ch_list[DISPLAY_CHANNEL_IDX]]['harm_rms'][freq_idx] )
			y_max.append( ready_freq_data[ch_list[DISPLAY_CHANNEL_IDX]]['harm_max'][freq_idx] )
		
		# Установка новых значений Ampl
		for rect, h in zip(rects_ampl, y_ampl):
			rect.set_height(h)
		# Масштабирование Ampl
		y_min = min(y_ampl)*1.05
		y_ampl_min = 0 if y_min >= 0 else y_min
		y_ampl_max = max(y_ampl)*1.05
		axes[0].set_ylim([y_ampl_min, y_ampl_max])
		# Установка новых значений Max
		for rect, h in zip(rects_max, y_max):
			rect.set_height(h)
		# Масштабирование Max
		y_min = min(y_max)*1.05
		y_max_min = 0 if y_min >= 0 else y_min
		y_max_max = max(y_max)*1.05
		axes[1].set_ylim([y_max_min, y_max_max])
		fig.canvas.draw()

		plt.pause(0.5)

def waveform_plot(conn):
	'''
	Brief Построение графиков входного сигнала \n
	Param[in] *conn* канал передачи данных между основным и графическим процессами \n
	Return None \n
	'''
	# Установка частотного диапазона, заполнение массива частотных меток
	x = []
	time = 0.0
	for time_idx in range(0, ADC_SAMPLE_NUMBER):
		x.append(time)
		time = time + (1000 / 1024)
	adc_data = conn.recv()
	# Установка значений сигнала
	y_ch1 = []
	y_ch2 = []
	for time_idx in range(ADC_SAMPLE_NUMBER):
		y_ch1.append(adc_data[ch_list[0]]['data'][time_idx])
		y_ch2.append(adc_data[ch_list[1]]['data'][time_idx])

	# Настройка графиков
	fig, axes = plt.subplots(nrows=2, ncols=1)
	axes[0].set_xlabel('Время, мс')
	axes[0].set_ylabel('Канал 1, мВ')
	axes[0].set_facecolor('seashell')
	axes[0].set_title('Двоичные данные АЦП')
	axes[1].set_xlabel('Время, мс')
	axes[1].set_ylabel('Канал 2, мВ')
	axes[1].set_facecolor('seashell')
	fig.set_facecolor('floralwhite')
	fig.set_figwidth(12)    # ширина Figure
	fig.set_figheight(6)    # высота Figure
	rects_ch1 = axes[0].scatter(x, y_ch1, color='DarkSlateBlue', s=2)
	rects_ch2 = axes[1].scatter(x, y_ch2, color='SeaGreen', s=2)
	# Бесконечный цикл по отрисовке графиков
	while True:
		# Получение новых данных по каналу (Pipe), заполнение соотв. списков
		adc_data = conn.recv()
		time_obj = fattime.convert_from_fattime(adc_data['service']['timestamp'].to_bytes(4, 'little'))
		time_str = '{0:02d}:{1:02d}:{2:02d}'.format(time_obj['hour'], time_obj['min'], time_obj['sec'])
		date_str = '{0:02d}.{1:02d}.{2:02d}'.format(time_obj['day'], time_obj['mon'], time_obj['year'])
		axes[0].set_title('Двоичные данные АЦП, ' + time_str + ' ' + date_str)
		y_ch1 = []
		y_ch2 = []
		for time_idx in range(0, ADC_SAMPLE_NUMBER):
			y_ch1.append(adc_data[ch_list[0]]['data'][time_idx])
			y_ch2.append(adc_data[ch_list[1]]['data'][time_idx])
		if True:
			# Установка новых значений CH1
			rects_ch1.set_offsets(np.c_[x, y_ch1])
			# Масштабирование CH1
			y_min = min(y_ch1)*1.05
			y_ch1_min = 0 if y_min >= 0 else y_min
			y_max = max(y_ch1)*1.05
			y_ch1_max = 0 if y_max <= 0 else y_max
			axes[0].set_ylim([y_ch1_min, y_ch1_max])
			# Установка новых значений CH2
			rects_ch2.set_offsets(np.c_[x, y_ch2])
			# Масштабирование CH2
			y_min = min(y_ch2)*1.05
			y_ch2_min = 0 if y_min >= 0 else y_min
			y_max = max(y_ch2)*1.05
			y_ch2_max = 0 if y_max <= 0 else y_max
			axes[1].set_ylim([y_ch2_min, y_ch2_max])
		else:
			rects_ch1 = axes[0].plot(x, y_ch1, color='DarkSlateBlue', ms=2)
			rects_ch2 = axes[1].plot(x, y_ch2, color='SeaGreen', ms=2)
		fig.canvas.draw()

		plt.pause(0.5)