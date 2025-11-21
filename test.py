from common.ko_util import korean_to_english_pronunciation

sample = ['안녕하세요', '반갑습니다', '빨간색 코끼리를 선택하세요']

for txt in sample:
    print(txt)
    print(korean_to_english_pronunciation(txt))