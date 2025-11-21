def korean_to_english_pronunciation(text):
    """
    한국어를 영어 발음 표기로 변환하는 함수
    Args:
        text (str): 변환할 한국어 텍스트
    Returns:
        str: 영어 발음 표기
    """
    # 발음 매핑 사전
    pronunciation_map = {
        # 초성 (consonant initials)
        'ㄱ': 'g', 'ㄲ': 'kk', 'ㄴ': 'n', 'ㄷ': 'd', 'ㄸ': 'tt',
        'ㄹ': 'r', 'ㅁ': 'm', 'ㅂ': 'b', 'ㅃ': 'pp', 'ㅅ': 's',
        'ㅆ': 'ss', 'ㅇ': '', 'ㅈ': 'j', 'ㅉ': 'jj', 'ㅊ': 'ch',
        'ㅋ': 'k', 'ㅌ': 't', 'ㅍ': 'p', 'ㅎ': 'h',
        # 중성 (vowels)
        'ㅏ': 'a', 'ㅐ': 'ae', 'ㅑ': 'ya', 'ㅒ': 'yae', 'ㅓ': 'eo',
        'ㅔ': 'e', 'ㅕ': 'yeo', 'ㅖ': 'ye', 'ㅗ': 'o', 'ㅘ': 'wa',
        'ㅙ': 'wae', 'ㅚ': 'oe', 'ㅛ': 'yo', 'ㅜ': 'u', 'ㅝ': 'wo',
        'ㅞ': 'we', 'ㅟ': 'wi', 'ㅠ': 'yu', 'ㅡ': 'eu', 'ㅢ': 'ui',
        'ㅣ': 'i',
    }
    # 종성 (consonant finals)
    final_consonants = {
        'ㄱ': 'k', 'ㄲ': 'k', 'ㄳ': 'k', 'ㄴ': 'n',
        'ㄵ': 'n', 'ㄶ': 'n', 'ㄷ': 't', 'ㄹ': 'l',
        'ㄺ': 'k', 'ㄻ': 'm', 'ㄼ': 'p', 'ㄽ': 'l',
        'ㄾ': 'l', 'ㄿ': 'p', 'ㅀ': 'l', 'ㅁ': 'm',
        'ㅂ': 'p', 'ㅄ': 'p', 'ㅅ': 't', 'ㅆ': 't',
        'ㅇ': 'ng', 'ㅈ': 't', 'ㅊ': 't', 'ㅋ': 'k',
        'ㅌ': 't', 'ㅍ': 'p', 'ㅎ': 't'
    }
    # 초성, 중성, 종성 리스트
    CHO = ['ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 
           'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']
    JUNG = ['ㅏ', 'ㅐ', 'ㅑ', 'ㅒ', 'ㅓ', 'ㅔ', 'ㅕ', 'ㅖ', 'ㅗ', 'ㅘ', 'ㅙ', 
            'ㅚ', 'ㅛ', 'ㅜ', 'ㅝ', 'ㅞ', 'ㅟ', 'ㅠ', 'ㅡ', 'ㅢ', 'ㅣ']
    JONG = ['', 'ㄱ', 'ㄲ', 'ㄳ', 'ㄴ', 'ㄵ', 'ㄶ', 'ㄷ', 'ㄹ', 'ㄺ', 'ㄻ', 
            'ㄼ', 'ㄽ', 'ㄾ', 'ㄿ', 'ㅀ', 'ㅁ', 'ㅂ', 'ㅄ', 'ㅅ', 'ㅆ', 'ㅇ', 
            'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']
    def decompose_hangul(char):
        """한글 음절을 초성, 중성, 종성으로 분해"""
        code = ord(char) - 0xAC00
        # 한글 음절 범위 체크
        if code < 0 or code > 11171:
            return None
        cho_index = code // 588
        jung_index = (code % 588) // 28
        jong_index = code % 28
        return {
            'cho': CHO[cho_index],
            'jung': JUNG[jung_index],
            'jong': JONG[jong_index]
        }
    result = []
    for char in text:
        if char == ' ':
            result.append(' ')
            continue
        decomposed = decompose_hangul(char)
        if decomposed:
            syllable = ''
            # 초성 추가
            syllable += pronunciation_map.get(decomposed['cho'], decomposed['cho'])
            # 중성 추가
            syllable += pronunciation_map.get(decomposed['jung'], decomposed['jung'])
            # 종성 추가
            if decomposed['jong']:
                syllable += final_consonants.get(decomposed['jong'], decomposed['jong'])
            result.append(syllable)
        else:
            # 한글이 아닌 문자는 그대로 추가
            result.append(char)
    # 음절을 하이픈으로 연결
    pronunciation = '-'.join(result)
    # 공백 주변의 하이픈 정리
    pronunciation = pronunciation.replace('- ', ' ').replace(' -', ' ')
    return pronunciation