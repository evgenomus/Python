'''
## Обмен данными с устройством по шине ModBus
###### Функции для внешнего использования:
###### **read_diag** возвращает данные диагностики
###### **read_ffts_stream** возвращает данные частотного анализа, текущие данные из буфера FIFO
###### **read_ffts_saved** возвращает данные частотного анализа, прочитанные из карты памяти
###### **read_adc_saved** возвращает исходные данные АЦП, прочитанные из карты памяти
###### **set_time** устанавливает время компьютера на устройстве
'''
from pymodbus.client import ModbusSerialClient
import sched, time, fattime, skif_chart, modbus_data
from multiprocessing import Process, Pipe

mode = {
	'read_diag_stream': 1,         # Режим чтения текущих данных диагностики устройства
	'read_data':                   # Режим чтения:
		#'ffts_stream',                 # текущих данных частотного анализа (текущие)
		'ffts_saved',                 # данных частотного анализа из SD карты
		#'adc_saved',                  # бинарных данных АЦП из SD карты
		#0,
	'set_time': 0,                 # Установка времени компьютера при запуске программы
}
req_data_fat_time = fattime.convert_to_fattime({
	'sec': 0,
	'min': 54,
	'hour': 23,
	'day': 26,
	'mon': 2,
	'year': 2023,
})

MODBUS_BROADCAST_ID = 0            # Широковещательный адрес ModBus
MODBUS_SLAVE_ID = 42               # Индивидуальный адрес slave-устройства ModBus (платы с измерителем)
MODBUS_DIAG_ADDR =  0              # Стартовый адрес регистров диагностики
MODBUS_DIAG_SIZE = 13              # Кол-во регистров диагностики
MODBUS_CONTROL_ADDR = 64           # Стартовый адрес регистров управления
MODBUS_CONTROL_SIZE =  3           # Кол-во регистров управления
MODBUS_FFTS_RAM_ADDR = 256         # Стартовый адрес регистров с данными FFTS RAM
MODBUS_FFTS_SD_ADDR = 2304         # Стартовый адрес регистров с данными FFTS SD
MODBUS_ADC_SD_ADDR = 12000         # Стартовый адрес регистров с данными ADC SD

MODBUS_COMMAND_READ_FIFO = 0x0001  # Команда обновления указателя чтения FIFO
MODBUS_COMMAND_READ_FFTS = 0x0008  # Команда чтения результатов FFTS из SD карты в оперативную память
MODBUS_COMMAND_READ_ADC = 0x0010   # Команда чтения бинарных данных ADC из SD карты в оперативную память
MODBUS_COMMAND_SET_TIME = 0x0020   # Команда установки реального времени
FFTS_FIFO_SIZE = 12                # Максимальное кол-во фреймов данных частотного анализа в FIFO

MODBUS_STATUS_SD_FFTS = 0x0800          # Бит статуса: чтение FFTS из SD карты
MODBUS_STATUS_SD_ADC = 0x1000           # Бит статуса: чтение ADC из SD карты
MODBUS_STATUS_SD_FFTS_SUCC = 0x2000     # Бит статуса: статус операции чтения FFTS из SD карты
MODBUS_STATUS_SD_ADC_SUCC = 0x4000      # Бит статуса: статус операции чтения ADC из SD карты

g_old_time = 0

ch_list = ['ch1', 'ch2', 'ch3']

mb_request_sched = sched.scheduler(time.time, time.sleep)   # установка расписания для вызова функции
rtu_client = ModbusSerialClient(method='rtu', port='COM5', baudrate=115200, timeout=10, parity='N', stopbits=1)
rtu_client.connect()

def read_diag(rtu_client_local):
	'''
	Brief  Чтение данных диагностики \n
	Param[in] *rtu_client_local* класс с методами и данными ModBus для обращения к устройству \n
	Return Данные диагностики \n
	'''
	request_diag = rtu_client_local.read_holding_registers(MODBUS_DIAG_ADDR, MODBUS_DIAG_SIZE, MODBUS_SLAVE_ID)
	diag_data = modbus_data.parse_diag(request_diag)
	# Выведем в консоль результаты диагностики, игнорируя повторные значения (на основе сравнения меток времени)
	global g_old_time
	if g_old_time < diag_data['regs']['time']:
		print('Status BITS: ', diag_data['status'])
		print('Diagnostic REGS: ', diag_data['regs'])
	g_old_time = diag_data['regs']['time']
	return diag_data

def read_ffts(rtu_client_local, start_addr):
	'''
	Brief Чтение данных частотного анализа по протоколу ModBus RTU \n
	Param[in] *rtu_client_local* класс с методами и данными ModBus для обращения к устройству \n
	Param[in] *start_addr* стартовый адрес данных ModBus \n
	Return Набор регистров с данными частотного анализа \n
	'''
	FREQ_BLOCK_REG_COUNT = 96  # Кол-во анализируемых гармоник
	TIME_REG_COUNT = 2         # Кол-во регистров времени
	CH_REG_COUNT = FREQ_BLOCK_REG_COUNT * 4 + TIME_REG_COUNT  # Полное кол-во регистров частотного анализа для одного канала
	# Чтение набора регистров FFTS
	ffts_regs = {}
	for ch_idx in range(3):
		ch_name = ch_list[ch_idx]
		request_ffts = []
		for block_idx in range(4):
			request_ffts.append(rtu_client_local.read_holding_registers(start_addr + block_idx * FREQ_BLOCK_REG_COUNT + ch_idx * CH_REG_COUNT,\
				FREQ_BLOCK_REG_COUNT, MODBUS_SLAVE_ID))
		ffts_regs[ch_name] = request_ffts
	# Прочитаем текущую метку времени и обновим указатель чтения
	if MODBUS_FFTS_RAM_ADDR == start_addr:
		request_time = rtu_client_local.read_holding_registers(256 + (block_idx + 1) * FREQ_BLOCK_REG_COUNT, TIME_REG_COUNT, MODBUS_SLAVE_ID)
		ffts_regs['time'] = request_time.registers[int(0)] + (request_time.registers[int(1)] << 16)
		request_read_fifo_ptr = rtu_client_local.write_registers(MODBUS_CONTROL_ADDR, [MODBUS_COMMAND_READ_FIFO], MODBUS_SLAVE_ID)
	else:
		ffts_regs['time'] = 0
	return ffts_regs

def read_ffts_stream(rtu_client_local):
	'''
	Brief Чтение текущих данных частотного анализа устройства \n
	Param[in] *rtu_client_local* класс с методами и данными ModBus для обращения к устройству \n
	Return Объект с данные частотного анализа \n
	'''
	ffts_regs = read_ffts(rtu_client_local, MODBUS_FFTS_RAM_ADDR)
	return modbus_data.parse_ffts(ffts_regs)

def read_ffts_saved(rtu_client_local, time_stamp):
	'''
	Brief  Чтение данных частотного анализа, сохранненых на карте памяти SD \n
	Param[in] *rtu_client_local* класс с методами и данными ModBus для обращения к устройству \n
	Param[in] *time_stamp* временная метка запрашиваемых данных \n
	Return Объект с данными частотного анализа или 0 (в случае ошибки) \n
	'''
	read_ffts_regs = []
	read_ffts_regs.append(MODBUS_COMMAND_READ_FFTS)
	read_ffts_regs.append(time_stamp & 0x0000FFFF)
	read_ffts_regs.append((time_stamp & 0xFFFF0000) >> 16)
	rtu_client_local.write_registers(MODBUS_CONTROL_ADDR, read_ffts_regs, MODBUS_SLAVE_ID)
	# Проверка завершения чтения FFTS из SD карты в RAM буфер. Если данные готовы, то прочитаем их
	time.sleep(0.01)
	request_status = rtu_client_local.read_holding_registers(MODBUS_DIAG_ADDR, 1, MODBUS_SLAVE_ID)
	if 0 == (request_status.registers[int(0)] & MODBUS_STATUS_SD_FFTS) and 0 == (request_status.registers[int(0)] & MODBUS_STATUS_SD_FFTS_SUCC):
		ffts_regs = read_ffts(rtu_client_local, MODBUS_FFTS_SD_ADDR)
		return modbus_data.parse_ffts(ffts_regs)
	else:
		return 0

def read_adc_saved(rtu_client_local, time_stamp):
	'''
	Brief  Чтение бинарных данных АЦП, сохраненных на карте памяти SD. Прочитаем 8200 * 3 = 24600 байт (12300 регистров) \n
	Param[in] *rtu_client_local* класс с методами и данными ModBus для обращения к устройству \n
	Param[in] *time_stamp* временная метка запрашиваемых данных \n
	Return Объект с данными АЦП или 0 (в случае ошибки) \n
	'''
	read_adc_regs = []
	read_adc_regs.append(MODBUS_COMMAND_READ_ADC)
	read_adc_regs.append(time_stamp & 0x0000FFFF)
	read_adc_regs.append((time_stamp & 0xFFFF0000) >> 16)
	rtu_client_local.write_registers(MODBUS_CONTROL_ADDR, read_adc_regs, MODBUS_SLAVE_ID)
	# Проверка завершения чтения данных ADC из SD карты в RAM буфер. Если данные готовы, то прочитаем их
	time.sleep(0.03)
	request_status = rtu_client_local.read_holding_registers(MODBUS_DIAG_ADDR, 1, MODBUS_SLAVE_ID)
	if 0 == (request_status.registers[int(0)] & MODBUS_STATUS_SD_ADC) and 0 == (request_status.registers[int(0)] & MODBUS_STATUS_SD_ADC_SUCC):
		# Прочитаем данные АЦП, переписанные с карты памяти в RAM-буфер (100 блоков по 123 16-битных регистра)
		BLOCK_SIZE = 123
		BLOCK_COUNT = 100
		adc_data_regs = []
		for block_idx in range(BLOCK_COUNT):
			block_data = rtu_client_local.read_holding_registers(MODBUS_ADC_SD_ADDR + block_idx * BLOCK_SIZE,\
					BLOCK_SIZE, MODBUS_SLAVE_ID)
			for reg_idx in range(BLOCK_SIZE):
				adc_data_regs.append(block_data.registers[reg_idx])
		return modbus_data.parse_adc(adc_data_regs, time_stamp)
	else:
		return 0

def set_time(rtu_client_local):
	'''
	Brief  Установка времени компьютера на устройстве \n
	Param[in] *rtu_client_local* класс с методами и данными ModBus для обращения к устройству \n
	Return None \n
	'''
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
	fat_time_regs.append(MODBUS_COMMAND_SET_TIME)
	fat_time_regs.append(fat_time & 0x0000FFFF)
	fat_time_regs.append((fat_time & 0xFFFF0000) >> 16)
	rtu_client_local.write_registers(MODBUS_CONTROL_ADDR, fat_time_regs, MODBUS_BROADCAST_ID)

def mb_request_func(parent_conn):
	'''
	Brief  Чтение всех данных устройства по шине ModBus (данных FFTS, ADC диагностики) \n
	Param[in] *parent_conn* канал передачи данных (pipe) между основным и графическим процессами \n
	Return None \n
	'''
	mb_request_sched.enter(1, 1, mb_request_func, argument=(parent_conn,))  # Перезапуск через 1 сек
	# Чтение текущих данных частотного анализа FFTS
	if 'ffts_stream' == mode['read_data']:
		fifo_level = FFTS_FIFO_SIZE - 1
		while fifo_level > 2:
			# Прочитаем данные диагностики
			diag_data = read_diag(rtu_client)
			fifo_level = diag_data['regs']['fifo_level']
			# Прочитаем данные частотного анализа и отправим в графический модуль
			if diag_data['regs']['fifo_wr'] != (diag_data['regs']['fifo_rd'] + 1):
				read_ffts_stream(rtu_client)
		parent_conn.send(read_ffts_stream(rtu_client))
	# Запрос диагностики и вывод в консоль
	if 1 == mode['read_diag_stream']:
		diag_data = read_diag(rtu_client)
	# Прочитаем данные, сохраненные на SD карту: результаты преобразования FFTS или  бинарные данные АЦП
	if 'ffts_saved'== mode['read_data']:
		ffts_saved = read_ffts_saved(rtu_client, req_data_fat_time)
		if 0 == ffts_saved:
			print('FFTS data request error')
		else:
			ffts_saved['ch1']['time'] = req_data_fat_time
			ffts_saved['ch2']['time'] = req_data_fat_time
			ffts_saved['ch3']['time'] = req_data_fat_time
			parent_conn.send(ffts_saved)
	elif 'adc_saved' == mode['read_data']:
		adc_saved = read_adc_saved(rtu_client, req_data_fat_time)
		if 0 == adc_saved:
			print('ADC data request error')
		else:
			parent_conn.send(adc_saved)

def main():
	'''
	Brief  MAIN, запуск основных функций и процессов \n
	'''
	parent_conn, child_conn = Pipe()
	if 'ffts_stream' == mode['read_data'] or 'ffts_saved' == mode['read_data']:
		plot = Process(target=skif_chart.fft_plot, args=(child_conn,))
	elif 'adc_saved' == mode['read_data']:
		plot = Process(target=skif_chart.waveform_plot, args=(child_conn,))
	if 'ffts_stream' == mode['read_data'] or 'ffts_saved' == mode['read_data'] or 'adc_saved' == mode['read_data']:
		plot.start()
	#plt.show(block=False)

	# Установим время на удаленном устройстве (широковещательная команда на адрес 0)
	if 1 == mode['set_time']:
		set_time(rtu_client)

	mb_request_func(parent_conn)
	mb_request_sched.run()

if __name__ == '__main__':
	main()