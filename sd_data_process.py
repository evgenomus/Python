'''
## Конвертация данных SD карты в Excel. Вызов функций модулей adc_parse и diag_parse, пример работы с данными.
'''
import pandas as pd
import adc_parse, diag_parse, json
from datetime import datetime

DATA_MINUTE_START = 0 # {0..59} Минута, с которой начинается преобразование данных АЦП
DATA_MINUTE_NUMBER = 5 # {1..60} Кол-во минут для преобразования данных АЦП

all_data_int = adc_parse.main(DATA_MINUTE_START * 30, DATA_MINUTE_NUMBER * 30) #number of 2-sec buffers, 1800 max.

df = pd.DataFrame({
	'ChannelX': all_data_int[0],
	'ChannelY': all_data_int[1],
	'ChannelZ': all_data_int[2],
})

print('Converting to xlsx...')
start_datetime = datetime.now()
df.to_excel('./all_data.xlsx', sheet_name='adc')
finish_datetime = datetime.now()
print('>__ Data convert time is ' + str(finish_datetime - start_datetime))

DIAG_FRAME_COUNT = 1800 # Кол-во фреймов диагностики

all_data_diag = diag_parse.main(DIAG_FRAME_COUNT) #number of 2-sec buffers, 1800 max.
#Выделим напряжения, кратные основной частоте фрейма (каждое 20-е)
inp_voltage_cut = []
for frame_idx in range(DIAG_FRAME_COUNT):
	inp_voltage_cut.append(all_data_diag['inp_voltage'][frame_idx * 20])
#Преобразуем время в понятный текстовый формат
time_stamps = []
for frame_idx in  range(DIAG_FRAME_COUNT):
	time_str = \
		str(all_data_diag['frame_time'][frame_idx]['hour']).zfill(2) + ':' +\
		str(all_data_diag['frame_time'][frame_idx]['min']).zfill(2) + ':' +\
		str(all_data_diag['frame_time'][frame_idx]['sec']).zfill(2)
	time_stamps.append(time_str)

df = pd.DataFrame({
	'Time': time_stamps,
	'Humi Int': all_data_diag['hum_int'],
	'Temp Int': all_data_diag['temp_int'],
	'Humi Ext': all_data_diag['hum_ext'],
	'Temp Ext': all_data_diag['temp_ext'],
	'Input Vlt': inp_voltage_cut,
})

print('Converting to xlsx...')
start_datetime = datetime.now()
df.to_excel('./diag_data.xlsx', sheet_name='diag')
finish_datetime = datetime.now()
print('>__ Data convert time is ' + str(finish_datetime - start_datetime))
pass