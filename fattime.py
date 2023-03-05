'''
# Преобразование форматов времени
'''
fat_time_offs = {
	'sec': 1,
	'min': 5,
	'hour': 11,
	'day': 16,
	'mon': 21,
	'year': 25,
}
fat_time_mask = {
	'sec': 0x0000001F,
	'min': 0x000007E0,
	'hour': 0x0000F800,
	'day': 0x001F0000,
	'mon': 0x01E00000,
	'year': 0xFE000000,
}

def convert_from_fattime(time_buffer):
	'''
	Brief Преобразование временной метки из uint32_t в словарь со значениями секунд, минут, и т.д. \n
	Param[in] *time_buffer* временная метка в формате FAT_TIME \n
	Return Временная метка в формате словаря с секундами, минутами, и т.д. \n
	'''
	timestamp_int = int.from_bytes(time_buffer, byteorder = 'little', signed = False)

	timestamp = {
		'sec': 0,
		'min': 0,
		'hour': 0,
		'day': 0,
		'mon': 0,
		'year': 0,
	}
	timestamp['sec'] = (timestamp_int & fat_time_mask['sec']) << fat_time_offs['sec']
	timestamp['min'] = (timestamp_int & fat_time_mask['min']) >> fat_time_offs['min']
	timestamp['hour'] = (timestamp_int & fat_time_mask['hour']) >> fat_time_offs['hour']
	timestamp['day'] = (timestamp_int & fat_time_mask['day']) >> fat_time_offs['day']
	timestamp['mon'] = ((timestamp_int & fat_time_mask['mon']) >> fat_time_offs['mon']) - 1
	timestamp['year'] = ((timestamp_int & fat_time_mask['year']) >> fat_time_offs['year']) + 1980

	return timestamp
	
def convert_to_fattime(timestamp):
	'''
	Brief Преобразование временной метки из словаря со значениями секунд, минут, и т.д. - в значение uint32_t (FAT_TIME format) \n
	Param[in] *timestamp* временная метка в формате словаря с секундами, минутами, и т.д. \n
	Return Временная метка в формате FAT_TIME \n
	'''
	fattime = 0
	fattime = fattime | ((timestamp['sec'] >> fat_time_offs['sec']) & fat_time_mask['sec'])
	fattime = fattime | ((timestamp['min'] << fat_time_offs['min']) & fat_time_mask['min'])
	fattime = fattime | ((timestamp['hour'] << fat_time_offs['hour']) & fat_time_mask['hour'])
	fattime = fattime | ((timestamp['day'] << fat_time_offs['day']) & fat_time_mask['day'])
	fattime = fattime | (((timestamp['mon'] + 1) << fat_time_offs['mon']) & fat_time_mask['mon'])
	fattime = fattime | (((timestamp['year'] - 1980) << fat_time_offs['year']) & fat_time_mask['year'])

	return fattime