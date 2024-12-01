import json
import os
import time
import pandas as pd
from bs4 import BeautifulSoup
import requests
import datetime as dt
from tqdm import tqdm


def get_count_product(parameters: dict) -> int:
    counts = requests.get('https://api.kufar.by/search-api/v2/search/count', params=parameters)
    count_products = counts.json()['count']

    return int(count_products)


def get_request_parameters_and_filename(url: str) -> (dict, int, str) or int:

    try:
        main_page = requests.get(url)
    except requests.exceptions.MissingSchema:
        print('Ошибка: Вы ввели неверную ссылку',end='\n\n')
        return 0
    except requests.exceptions.ConnectionError:
        print('Ошибка: Отсутствует подключение к интернету',end='\n\n')
        return 0

    soup = BeautifulSoup(main_page.text, 'html.parser')

    try:
        cat_name = soup.find('span',
                             class_="styles_link__text__yW1k7 styles_link__text--menu-tree__jVaR7 "
                                    "styles_link__text--menu-tree--active__6niOl").text
    except AttributeError:
        cat_name = 'kufar'

    main_info = soup.find('script', type="application/json")

    load = {
        'lang': 'ru',
    }

    json_data = json.loads(main_info.string)

    query_data = json_data.get("props").get("initialState").get("router").get("query")

    info = {}
    for key, value in query_data.items():
        if key in ['cepсt', 'ot', 'query', 'prc', 'ar', 'prn', 'rgn', 'cat']:
            if value:
                info[key] = value

    if info:
        load.update(info)

    if len(load) == 1:
        params = {'sort': 'lst.d'}
        params.update(load)
        count_products = get_count_product(params)
    else:
        count_products = get_count_product(load)

    load['size'] = 200

    return load, count_products, cat_name


def get_user_count(count_products: int, user_count: str) -> int:
    if not user_count or int(user_count) > count_products:
        return count_products
    else:
        return int(user_count)


def data_preparation(parameters: dict, user_count: int) -> dict:

    prod = {'Название': [], 'Цена': [], 'Категория': [], 'Состояние': [], 'Ссылка': []}

    count_product_in_base = 0

    with tqdm(total=user_count, desc="Загрузка объявлений",
              bar_format="{desc}: {percentage:3.0f}% |{bar}| {n_fmt}/{total_fmt}", ncols=80) as pbar:
        while True:
            data = requests.get('https://api.kufar.by/search-api/v2/search/rendered-paginated', params=parameters)

            json_data = data.json()['ads']
            pr_on_page = {'Название': [], 'Цена': [], 'Категория': [], 'Состояние': [], 'Ссылка': []}

            for i in json_data:
                if i['ad_link'] in prod['Ссылка']:
                    continue
                pr_on_page['Ссылка'].append(i['ad_link'])
                pr_on_page['Название'].append(i['subject'])
                price = int(i['price_byn']) / 100
                pr_on_page['Цена'].append(price if price else 'Договорная')

                flag = 0
                for j in i['ad_parameters']:

                    if j['pl'] in ['Подкатегория', 'Категория', 'Состояние']:
                        if j['pl'] == 'Подкатегория':
                            pr_on_page['Категория'].append(j['vl'])
                        else:
                            pr_on_page[j['pl']].append(j['vl'])
                        flag += 1

                if flag != 2:
                    pr_on_page['Состояние'].append('-')

                count_product_in_base += 1
                pbar.update(1)

                if count_product_in_base == user_count:
                    return prod

            for key in prod.keys():
                prod[key] += pr_on_page[key]

            for i in data.json()['pagination']['pages']:
                if i['label'] == 'next':
                    parameters['cursor'] = i['token']
                    break
            else:
                print('!Внимание! Какие-то неполадки с kufar', f'Загруженно {count_product_in_base} обьявлений', sep='\n')
                pbar.update(user_count - count_product_in_base)
                return prod


def create_dir(name_dir: str):
    if not os.path.isdir(name_dir):
        os.mkdir(name_dir)


def download_in_excel(items: dict, filename: str, name_dir: str):
    create_dir(name_dir)
    product = pd.DataFrame(items)
    writer = pd.ExcelWriter(f'{name_dir}/{filename} ({dt.datetime.now().strftime("%Y.%m.%d %H-%M-%S")}).xlsx')
    product.to_excel(writer, sheet_name='kufar', index=False)

    workbook = writer.book
    right_align_format = workbook.add_format({'align': 'center'})

    writer.sheets['kufar'].set_column(0, 1, width=50)
    writer.sheets['kufar'].set_column(1, 2, width=15, cell_format=right_align_format)
    writer.sheets['kufar'].set_column(2, 3, width=40, cell_format=right_align_format)
    writer.sheets['kufar'].set_column(3, 4, width=10)
    writer.sheets['kufar'].set_column(4, 5, width=40)

    writer.close()


def get_data_from_the_user() -> (str,str) or int:
    url = input('Введите ссылку: ')

    if url == 'exit':
        return 0
    elif 'kufar.by' not in url:
        print('Ошибка: Вы ввели неверную ссылку', end='\n\n')
        return 1

    try:
        size_data = input('Введите кол-во товара или нажмите Enter (если хотите всё): ')
        if size_data == 'exit':
            return 0
        elif size_data == '':
            return url, size_data
        elif int(size_data) <= 0:
            raise ValueError

    except ValueError:
        print('Ошибка: Вы ввели неверное кол-во товара', end='\n\n')
        return 1

    return url, size_data


def main():
    print('!!!Для выхода напишите exit!!!')
    while True:
        start_data = get_data_from_the_user()

        if not start_data:
            return

        if start_data == 1:
            continue

        start = time.time()
        data = get_request_parameters_and_filename(start_data[0])

        if not data:
            continue

        print(f'Всего обьявлений в этой категории: {data[1]}')
        user_count = get_user_count(data[1], start_data[1])

        prod = data_preparation(data[0], user_count)
        download_in_excel(prod, data[2], 'Товары_куфар')

        print(f'Время выполнения: {round(time.time() - start, 2)} секунд', end='\n\n')


main()