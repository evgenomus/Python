# Обмен данными с устройством по шине ModBus
from pymodbus.client import ModbusSerialClient
import sched, time, fattime
import numpy as np
import matplotlib.pyplot as plt
from multiprocessing import Process, Pipe

MODBUS_BROADCAST_ID = 0        # Широковещательный адрес ModBus
MODBUS_SLAVE_ID = 42           # Индивидуальный адрес slave-устройства ModBus (платы с измерителем)
MODBUS_DIAG_SIZE = 13          # Кол-во регистров диагностики

ONLY_POSITIVE_VALUES = True    # Конвертировать отрицательные значения амплитуд и фаз в положительные
FFT_RANGE1_START =    0     # 0..20 Hz range start
FFT_RANGE1_STOP  =   39     # 0..20 Hz range stop */
FFT_RANGE1_STEP  =    1     # 0..20 Hz range step 0.5Hz */
FFT_RANGE2_START =   40     # 20..50 Hz range start */
FFT_RANGE2_STOP  =   99     # 20..50 Hz range stop */
FFT_RANGE2_STEP  =    2     # 20..50 Hz range step 1.0Hz */
FFT_RANGE3_START =  100     # 50..100 Hz range start */
FFT_RANGE3_STOP  =  200     # 50..100 Hz range stop */
FFT_RANGE3_STEP  =    4     # 50..100 Hz range step 2Hz */
FFT_LENGTH_RANGE1 = int(((FFT_RANGE1_STOP-FFT_RANGE1_START) / FFT_RANGE1_STEP) + 1)  # 40, первый частотный диапазон */
FFT_LENGTH_RANGE2 = int(((FFT_RANGE2_STOP-FFT_RANGE2_START) / FFT_RANGE2_STEP) + 1)  # 30, второй частотный диапазон */
FFT_LENGTH_RANGE3 = int(((FFT_RANGE3_STOP-FFT_RANGE3_START) / FFT_RANGE3_STEP) + 1)  # 26, третий частотный диапазон */
FFT_LENGTH_SHORT = FFT_LENGTH_RANGE1 + FFT_LENGTH_RANGE2 + FFT_LENGTH_RANGE3         # 96, кол-во передаваемых гармоник */

COMMAND_READ_FIFO_UPDATE = 0x0001
DISPLAY_CHANNEL_IDX = 0 # {0..2}: канал, данные которого отображаются на графике

ch_list = ['ch1', 'ch2', 'ch3']
g_old_time = 0

mb_request_sched = sched.scheduler(time.time, time.sleep)   # установка расписания для вызова функции
rtu_client = ModbusSerialClient(method='rtu', port='COM5', baudrate=115200, timeout=10, parity='N', stopbits=1)
rtu_client.connect()

'''
	* @brief  Разбор данных диагностики, полученных по ModBus
	* @param[in] request_diag принятые данные ModBus
	* @return Словарь регистров диагностики и битов статуса устройства
'''
def parse_diag(request_diag):
	diag_regs = {
		'status': 0,
		'time': 0,
		'hum_int': 0,
		'temp_int': 0,
		'hum_ext': 0,
		'temp_ext': 0,
		'inp_vlt': 0,
		'sd_total': 0,
		'sd_free': 0,
		'fifo_wr': 0,
		'fifo_rd': 0,
		'version': ''
	}
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
	diag_regs['version'] = 'v{0}.{1}.{2}'.format( ((request_diag.registers[int(12)] & 0xF000) >> 12),
		((request_diag.registers[int(12)] & 0x0FF0) >> 4), ((request_diag.registers[int(12)] & 0x000F) >> 0))
	
	diag_status = {
		'sync': 0 if 0 == (diag_regs['status'] & 0x0001) else 1,
		'pwr_ok': 0 if 0 == (diag_regs['status'] & 0x0002) else 1,
		'sd_ok': 0 if 0 == (diag_regs['status'] & 0x0004) else 1,
		'rtc_ok': 0 if 0 == (diag_regs['status'] & 0x0008) else 1,
		'env_int': 0 if 0 == (diag_regs['status'] & 0x0010) else 1,
		'env_ext': 0 if 0 == (diag_regs['status'] & 0x0020) else 1,
		'fifo_over': 0 if 0 == (diag_regs['status'] & 0x0100) else 1,
		'fifo_under': 0 if 0 == (diag_regs['status'] & 0x0200) else 1,
		'sd_full': 0 if 0 == (diag_regs['status'] & 0x0400) else 1,
	}
	
	return {'regs': diag_regs, 'status': diag_status}

'''
	* @brief  Построение графиков частотного анализа
	* @param[in] conn канал передачи данных между основным и графическим процессами
	* @return None
'''
def graph_plot(conn):
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
	# Установка значений гармоник (действительные и вещественные)
	y_real = []
	y_imag = []
	for freq_idx in range(FFT_LENGTH_SHORT):
		y_real.append(ready_freq_data[ch_list[DISPLAY_CHANNEL_IDX]]['real'][freq_idx])
		y_imag.append(ready_freq_data[ch_list[DISPLAY_CHANNEL_IDX]]['imag'][freq_idx])

	# Настройка графиков
	fig, axes = plt.subplots(nrows=2, ncols=1)
	axes[0].set_xlabel('Частота, Гц')
	axes[0].set_ylabel('Амплитуда гармоники (Real)')
	axes[0].set_facecolor('seashell')
	axes[0].set_title('Канал {0}'.format(ch_list[DISPLAY_CHANNEL_IDX]))
	axes[1].set_xlabel('Частота, Гц')
	axes[1].set_ylabel('Фаза гармоники (Imag)')
	axes[1].set_facecolor('seashell')
	fig.set_facecolor('floralwhite')
	fig.set_figwidth(12)    #  ширина Figure
	fig.set_figheight(6)    #  высота Figure
	rects_real = axes[0].bar(x, y_real, color='DarkSlateBlue', width = 0.4)
	rects_image = axes[1].bar(x, y_imag, color='SeaGreen', width = 0.4)

	# Бесконечный цикл по отрисовке графиков
	while True:
		# Получение новых данных по каналу (Pipe), заполнение соотв. списков
		ready_freq_data = conn.recv()
		y_real = []
		y_imag = []
		for freq_idx in range(FFT_LENGTH_SHORT):
			y_real_curr = ready_freq_data[ch_list[DISPLAY_CHANNEL_IDX]]['real'][freq_idx]
			y_imag_curr = ready_freq_data[ch_list[DISPLAY_CHANNEL_IDX]]['imag'][freq_idx]
			if True == ONLY_POSITIVE_VALUES:
				y_real_curr = abs(y_real_curr)
				y_imag_curr = abs(y_imag_curr)
			y_real.append(y_real_curr)
			y_imag.append(y_imag_curr)
		if True:
			# Установка новых значений Real
			for rect, h in zip(rects_real, y_real):
				rect.set_height(h)
			# Масштабирование Real
			y_min = min(y_real)*1.05
			y_real_min = 0 if y_min >= 0 else y_min
			y_real_max = max(y_real)*1.05
			axes[0].set_ylim([y_real_min, y_real_max])
			# Установка новых значений Imag
			for rect, h in zip(rects_image, y_imag):
				rect.set_height(h)
			# Масштабирование Imag
			y_min = min(y_imag)*1.05
			y_imag_min = 0 if y_min >= 0 else y_min
			y_imag_max = max(y_imag)*1.05
			axes[1].set_ylim([y_imag_min, y_imag_max])
		else:
			rects_real = axes[0].bar(x, y_real, color='DarkSlateBlue', width = 0.4)
			rects_image = axes[1].bar(x, y_imag, color='SeaGreen', width = 0.4)
		fig.canvas.draw()

		plt.pause(0.5)

'''
	* @brief  Чтение всех оперативных параметров устройства по шине ModBus (данных FFTS и диагностики)
	* @param[in] parent_conn канал передачи данных между основным и графическим процессами
	* @return None
'''
def mb_request_func(parent_conn):
	mb_request_sched.enter(1, 1, mb_request_func, argument=(parent_conn,))  # Перезапуск через 1 сек
	# Прочитаем данные диагностики
	request_diag = rtu_client.read_holding_registers(0, MODBUS_DIAG_SIZE, MODBUS_SLAVE_ID)
	diag_data = parse_diag(request_diag)
	# Выведем в консоль результаты диагностики, игнорируя повторные значения (на основе сравнения меток времени)
	global g_old_time
	if g_old_time < diag_data['regs']['time']:
		print(diag_data['status'])
		print(diag_data['regs'])
	g_old_time = diag_data['regs']['time']

	# Прочитаем данные частотного анализа
	freq_data = {
		'ch1': {
			'real': [],	'imag': [], 'time' : [],
		},
		'ch2': {
			'real': [],	'imag': [],	'time' : [],
		},
		'ch3': {
			'real': [],	'imag': [],	'time' : [],
		},
	}
	FREQ_BLOCK_REG_COUNT = 96  # Кол-во анализируемых гармоник
	TIME_REG_COUNT = 2         # Кол-во регистров времени
	CH_REG_COUNT = FREQ_BLOCK_REG_COUNT * 4 + TIME_REG_COUNT  # Полное кол-во регистров частотного анализа для одного канала
	new_data_flag = False
	if diag_data['regs']['fifo_wr'] != (diag_data['regs']['fifo_rd'] + 1):
		new_data_flag = True
		for ch_idx in range(3):
			ch_name = ch_list[ch_idx]
			request_ffts = []
			for block_idx in range(4):
				request_ffts.append(rtu_client.read_holding_registers(256 + block_idx * FREQ_BLOCK_REG_COUNT + ch_idx * CH_REG_COUNT, FREQ_BLOCK_REG_COUNT, MODBUS_SLAVE_ID))
				for harm_idx in range(int(FREQ_BLOCK_REG_COUNT / 2)):
					real_bytes = []
					real_bytes.append( (request_ffts[block_idx].registers[(harm_idx * 2) + 0] & 0x00FF) >> 0 )
					real_bytes.append( (request_ffts[block_idx].registers[(harm_idx * 2) + 0] & 0xFF00) >> 8 )
					real_bytes.append( (request_ffts[block_idx].registers[(harm_idx * 2) + 1] & 0x00FF) >> 0 )
					real_bytes.append( (request_ffts[block_idx].registers[(harm_idx * 2) + 1] & 0xFF00) >> 8 )
					real_bytes_np = np.array(real_bytes, dtype=np.uint8)
					real_as_float = real_bytes_np.view(dtype=np.float32)
					#print('real[', harm_idx + (block_idx * 24), '] = ', real_as_float)
					if block_idx < 2:
						freq_data[ch_name]['real'].append(real_as_float[0])
					elif block_idx < 4:
						freq_data[ch_name]['imag'].append(real_as_float[0])
			# Прочитаем текущую метку времени
			request_time = rtu_client.read_holding_registers(256 + (block_idx + 1) * FREQ_BLOCK_REG_COUNT, TIME_REG_COUNT, MODBUS_SLAVE_ID)
			freq_data[ch_name]['time'] = request_time.registers[int(0)] + (request_time.registers[int(1)] << 16)
		# Обновим указатель чтения
		request_read_fifo_ptr = rtu_client.write_registers(1, [COMMAND_READ_FIFO_UPDATE], MODBUS_SLAVE_ID)
		# Передадим данные в графический процесс
		parent_conn.send(freq_data)

'''
	* @brief  Установка времени комьпютера на устройстве
	* @return None
'''
def set_time():
	time_struct = time.localtime(time.time())
	fat_time = fattime.convert_to_fattime({
		'sec': time_struct.tm_sec,
		'min': time_struct.tm_min,
		'hour': time_struct.tm_hour,
		'day': time_struct.tm_mday,
		'mon': time_struct.tm_mon,
		'year': time_struct.tm_year,
	})
	fat_time_regs = []
	fat_time_regs.append((fat_time & 0xFFFF0000) >> 16)
	fat_time_regs.append(fat_time & 0x0000FFFF)
	rtu_client.write_registers(2, fat_time_regs, MODBUS_BROADCAST_ID)

#MAIN, запуск основных функций и процессов
def main():
	#set_time()
	parent_conn, child_conn = Pipe()
	plot = Process(target=graph_plot, args=(child_conn,))
	plot.start()
	plt.show(block=False)

	mb_request_func(parent_conn)
	mb_request_sched.run()

if __name__ == '__main__':
	main()