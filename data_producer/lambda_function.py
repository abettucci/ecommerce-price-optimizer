import json
import pandas as pd
import requests
import statistics
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
from datetime import datetime, timedelta
from gspread.utils import rowcol_to_a1
from gspread.exceptions import APIError
import pytz
from cachetools import cached, TTLCache
from googleapiclient.errors import HttpError
import boto3
from botocore.exceptions import ClientError
from opensearchpy import OpenSearch

def lambda_handler(event, context):
    """Sample pure Lambda function

    Parameters
    ----------
    event: dict, required
        API Gateway Lambda Proxy Input Format

        Event doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#api-gateway-simple-proxy-for-lambda-input-format

    context: object, required
        Lambda Context runtime methods and attributes

        Context doc: https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html

    Returns
    ------
    API Gateway Lambda Proxy Output Format: dict

        Return doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html
    """

    def put_price_update(worksheet_tokens_mio, df_promociones, product_id, new_price, token_de_acceso):
        fila = df_promociones.loc[df_promociones['Publicacion (id)'] == product_id[3:]].index
        tiene_promo = df_promociones.loc[df_promociones['Publicacion (id)'] == product_id[3:]]['Activo'].iloc[0] 

        if tiene_promo == '1':
            # Chequeo que la promo esté en fecha, si se venció, le pongo un 0 en 'Activo'
            buenos_aires_timezone = pytz.timezone('America/Argentina/Buenos_Aires')
            current_time = datetime.now(buenos_aires_timezone).strftime('%Y-%m-%d %H:%M:%S')
            current_time = datetime.strptime(current_time, "%Y-%m-%d %H:%M:%S")
            current_time = current_time.strftime("%m/%d/%Y")
            current_time = datetime.strptime(current_time, "%m/%d/%Y")
            t_expiracion = df_promociones.loc[df_promociones['Publicacion (id)'] == product_id[3:]]['Activa hasta'].iloc[0]
            t_expiracion = datetime.strptime(t_expiracion, "%m/%d/%Y")

            if current_time > t_expiracion:
                worksheet_tokens_mio.update_cell(fila, 8, '0')
                descuento = 0
            else:
                descuento = df_promociones.loc[df_promociones['Publicacion (id)'] == product_id[3:]]['Descuento (%)'].iloc[0]
                descuento_decimal = int(''.join(char for char in descuento if char.isdigit()))/100
                new_price = new_price/(1-descuento_decimal)
        return None


        # url = f"https://api.mercadolibre.com/items/{product_id}"
        # payload = json.dumps({"price": new_price})
        # headers = {'Authorization': 'Bearer ' + token_de_acceso,
        #         'Content-Type': 'application/json',
        #         'Accept': 'application/json'}
        # response = requests.request("PUT", url, headers=headers, data=payload)
        # return response.json()

    def remove_outliers_zscore(sample):
        sample_mean = sum(sample) / len(sample)
        sample_std = (sum((x - sample_mean) * 2 for x in sample) / len(sample)) * 0.5
        # Check if the standard deviation is zero
        if sample_std == 0:
            return sample  # No variation, return the original list
        z_scores = [(x - sample_mean) / sample_std for x in sample]
        # Set a threshold for outliers, e.g., 3 standard deviations away from the mean
        threshold = 3
        cleaned_sample = [x for x, z_score in zip(sample, z_scores) if abs(z_score) <= threshold]
        return cleaned_sample

    def index_and_transfer_from_s3_to_ecr():
        # Extract the bucket and object key from the S3 event
        bucket = 'my-meli-bucket'
        folder = 'price-optimizer-output'
        object_key = f'{folder}/optimizer-output-data.json'

        # Retrieve the data from S3
        response = s3_client.get_object(Bucket=bucket, Key=object_key)
        data = response['Body'].read().decode('utf-8')

        # Process the data (if needed) and convert it to a Python dictionary and index it into Amazon OpenSearch
        data_dict = json.loads(data)

        # Index the data into Amazon OpenSearch
        index_result = os_client.index(index='meli-optimizer-data2', body=data_dict)

        # Handle the index result as needed
        if index_result['result'] == 'created':
            # Data was successfully indexed
            return {
                'statusCode': 200,
                'body': 'Data retrieved and indexed successfully.'
            }
        else:
            # Handle errors
            return {
                'statusCode': 500,
                'body': 'Failed to index the data into OpenSearch.'
            }

    def get_product_gtin(token_de_acceso, product_id):
        gtin_value = ''
        url = f"https://api.mercadolibre.com/items/{product_id}?include_attributes=all"
        payload = {}
        headers = {'Authorization': token_de_acceso}
        response = requests.request("GET", url, headers=headers, data=payload)
        detalle_producto = response.json()
        atributos_producto = detalle_producto.get("attributes",[])
        for item in atributos_producto:
            if item['id'] == 'GTIN':
                gtin_value = item['value_name']
        return gtin_value

    def get_non_catalog_sellers(item_title, token_de_acceso):
            # Creo el objeto data con la info de la busqueda de MELI en JSON y lo parseo
            url = "https://api.mercadolibre.com/sites/MLA/search?q=" + item_title
            headers = {'Authorization': 'Bearer ' + token_de_acceso}
            response = requests.get(url, headers=headers)
            return response.json().get('results', [])

    def get_user_items(id_vendedor_propio, token_de_acceso):
        url2 = "https://api.mercadolibre.com/sites/MLA/search?seller_id=" + str(id_vendedor_propio)
        headers = {'Authorization': 'Bearer ' + token_de_acceso}
        response = requests.get(url2, headers=headers)
        return response.json().get('results', [])

    def get_user_id(token_de_acceso):
        url = "https://api.mercadolibre.com/users/me"
        payload = {}
        headers = {'Authorization': 'Bearer ' + token_de_acceso}
        response = requests.get(url, headers=headers, data=payload)
        return response.json()

    def make_read_api_call(funcion, parametros, hoja, slice1, slice2, google_api_dict_list):
        try:
            if funcion == 'open_by_key':
                resultado = hoja.open_by_key(parametros)
            if funcion == 'get_worksheet_by_id':
                resultado = hoja.get_worksheet_by_id(parametros)
            elif funcion == 'get_all_values':
                resultado = hoja.get_worksheet_by_id(parametros).get_all_values()
            else: #get_worksheet_by_id_and_get_all_values
                if slice2 == '':
                    resultado = hoja.get_worksheet_by_id(parametros).get_all_values()[slice1:]
                else:
                    resultado = hoja.get_worksheet_by_id(parametros).get_all_values()[slice1]
        except HttpError as e:
            if e.resp.status == 429:
                try:
                    creds = ServiceAccountCredentials.from_json_keyfile_dict(
                        google_api_dict_list[1], 
                        ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive'])
                    gc = gspread.authorize(creds) 
                    # sh = gc.open_by_key('1AbwRrOEFrcCXR2v8_djqckhLjJOM_2r8S1VwBwhS5Q0')

                    if funcion == 'open_by_key':
                        resultado = gc.open_by_key(parametros)
                    elif funcion == 'get_worksheet_by_id':
                        resultado = sh.get_worksheet_by_id(parametros)
                    elif funcion == 'get_all_values':
                        resultado = hoja.get_worksheet_by_id(parametros).get_all_values()
                    else: #get_worksheet_by_id_and_get_all_values
                        if slice2 == '':
                            resultado = hoja.get_worksheet_by_id(parametros).get_all_values()[slice1:]
                        else:
                            resultado = hoja.get_worksheet_by_id(parametros).get_all_values()[slice1]
                except:
                    if e.resp.status == 429:
                        # Handle rate limit exceeded error with exponential backoff
                        wait_time = 1  # Initial wait time in seconds
                        max_retries = 5  # Maximum number of retries
                        retries = 0

                        while retries < max_retries:
                            print(f"Rate limit exceeded. Waiting for {wait_time} seconds...")
                            time.sleep(wait_time)
                            try:
                                if funcion == 'open_by_key':
                                    resultado = gc.open_by_key(parametros)
                                elif funcion == 'get_worksheet_by_id':
                                    resultado = hoja.get_worksheet_by_id(parametros)
                                elif funcion == 'get_all_values':
                                    resultado = hoja.get_worksheet_by_id(parametros).get_all_values()
                                else: #get_worksheet_by_id_and_get_all_values
                                    resultado = hoja.get_worksheet_by_id(parametros).get_all_values()[slice1:slice2]
                                break
                            except HttpError as e:
                                if e.resp.status == 429:
                                    # Increase wait time exponentially for the next retry
                                    wait_time *= 2
                                    retries += 1
                                else:
                                    # Handle other HTTP errors
                                    raise
                    else:
                        # Handle other HTTP errors
                        raise
        return resultado

    def get_access_token(app_id, secret_client_id, refresh_token):
        url = "https://api.mercadolibre.com/oauth/token"
        payload = f"grant_type=refresh_token&client_id={app_id}&client_secret={secret_client_id}&refresh_token={refresh_token}"
        headers = {'accept': 'application/json','content-type': 'application/x-www-form-urlencoded'}
        response = requests.request("POST", url, headers=headers, data=payload)
        data = json.loads(response.text)
        proximo_refresh_token = data.get('refresh_token', None)
        access_token = data.get('access_token', None)
        t_expiracion = data.get('expires_in', None)
        return proximo_refresh_token, access_token, t_expiracion

    def get_user_data(id_vendedor, token_de_acceso):
        url = "https://api.mercadolibre.com/users/" + str(id_vendedor)
        payload = {}
        headers = {'Authorization': token_de_acceso}
        response = requests.get(url, headers=headers, data=payload)
        return response.json()

    def write_log_and_save_in_s3(cuenta_meli, my_product_id,
                                    producto, link, precio_minimo, precio_inicial, precio_actualizado,
                                    fecha_pingueo, fecha_actualizacion, posicion, mensaje, precio,
                                    runtime, llamados_api_mercadolibre, llamados_write_API_google,
                                    llamados_read_API_google, llamados_API_google, tiempo_ganando_en_minutos,
                                    id_vendedor, nickname_vendedor, stock_disponible, ventas_total,
                                    free_shipping, logistic_type, store_pick_up, provincia_ciudad,
                                    claims, ventas, delayed_handling_time, cancelaciones):
        data_to_upload = {
            "cuenta_mercadolibre" : cuenta_meli,
            "id_producto" : my_product_id, 
            "producto" : producto,
            "link" : link,
            "precio_minimo" : precio_minimo,
            "precio_inicial" : precio_inicial,
            "precio_actualizado" : precio_actualizado,
            "fecha_pingueo" : fecha_pingueo,
            "fecha_actualizacion" : fecha_actualizacion,
            "posicion" : posicion,
            "mensaje" : mensaje,
            "precio" : precio,
            "runtime" : runtime,
            "llamados_api_mercadolibre" : llamados_api_mercadolibre,
            "llamados_write_API_google" : llamados_write_API_google, 
            "llamados_read_API_google" : llamados_read_API_google,
            "llamados_API_google" : llamados_API_google,
            "tiempo_ganando_en_minutos" : tiempo_ganando_en_minutos,
            "id_vendedor" : id_vendedor,
            "nickname_vendedor" : nickname_vendedor,
            "stock_disponible" : stock_disponible,
            "ventas_total" : ventas_total,
            "free_shipping" : free_shipping,
            "logistic_type" : logistic_type,
            "store_pick_up" : store_pick_up,
            "provincia_ciudad" : provincia_ciudad,
            "claims" : claims,
            "ventas" : ventas,
            "delayed_handling_time" : delayed_handling_time,
            "cancelaciones" : cancelaciones
        }    

        print(data_to_upload) 
        
        data_string = json.dumps(data_to_upload)
        bucket_name = 'my-meli-bucket'
        object_key = 'price-optimizer-output/optimizer-output-data.json'  # Customize the object key as needed
        s3_client.put_object(Bucket=bucket_name, Key=object_key, Body=data_string)

    def get_min_price(catalog_id, stock_producto):
            max_price = 0
            # Leemos el Google Sheets para obtener los precios minimos
            worksheet_pmin = gc.open_by_key('1HkYGDx58viet_txow-OeXgqJg78RiZ44asusG7EyprQ').get_worksheet_by_id(131132256)
            header_cell = worksheet_pmin.find("Catalog id")
            start_cell = rowcol_to_a1(header_cell.row , header_cell.col)
            end_cell = rowcol_to_a1(worksheet_pmin.row_count, worksheet_pmin.col_count)
            data_range = f"{start_cell}:{end_cell}"
            all_values = worksheet_pmin.get(data_range)
            header_row = all_values[0]
            cell_values_pmin = []
            for row_values in all_values[1:]:
                row_dict = dict(zip(header_row, row_values))
                cell_values_pmin.append(row_dict)
            
            ### VER DE AUTOMATIZAR LA CREACION DE HOJAS EN EL LOG PARA LOS PRODUCTOS NUEVOS QUE APAREZCAN EN EL SHEET
            ### DE PRECIO MINIMO

            # Definimos la tabla de Id Publicacion, ..., Precio Minimo en un dataframe
            df = pd.DataFrame(cell_values_pmin[1:], columns=cell_values_pmin[0])

            # Analizamos dentro de que batch de producto nos encontramos segun el stock actual en MercadoLibre y sacamos el 
            # precio minimo correspondiente a ese batch
            matching_batch_values = []
            for index in df.index:
                row_data = df.loc[index]
                if row_data['Catalog id'] == catalog_id:
                    matching_batch_values.append(int(row_data['Unidades']))
                    for ind, batch_value in enumerate(matching_batch_values):
                        if stock_producto >= (float(sum(matching_batch_values)) - sum(matching_batch_values[:ind+1])):
                            filtered_df = df[(df['Catalog id'] == catalog_id) & (df['Unidades'] == str(matching_batch_values[ind]))]
                            max_price = float(pd.to_numeric(filtered_df['Pmin MELI c/ IIBB e IVA'].astype(str).str[1:].str.replace('.', '').str.replace(',', '.', regex=False), errors='coerce').iloc[0])
                            break
            return max_price

    def extract_last_2_chars(column_name):
            return column_name[-2:]

    # Funcion para formatear la tabla de tiempos minimo ganando para aumentar el precio
    def tiempos_minimos(df_tiempos_minimos):    
        df_tiempos_minimos.columns = df_tiempos_minimos.columns.str.replace(' hs', '').str.rstrip()
        formatted_columns = df_tiempos_minimos.columns[2:].map(extract_last_2_chars).tolist()
        columns_final = df_tiempos_minimos.columns[:2].tolist()
        append_items = lambda list_to_extend, items_to_append: list_to_extend.extend(items_to_append)
        append_items(columns_final, formatted_columns)
        columns_final = [col.replace('00', '24') if col == '00' else col for col in columns_final]
        df_tiempos_minimos.columns = columns_final
        return df_tiempos_minimos

    def get_item_attributes(product_id, access_token):
        url = f"https://api.mercadolibre.com/items/{product_id}"
        headers = {'Authorization': 'Bearer ' + access_token,
                'Content-Type': 'application/json',
                'Accept': 'application/json'}
        response = requests.request("GET", url, headers=headers, data={})
        return response.json()

    def get_attribute(item, index, default=""):
        try:
            return item['attributes'][index]['value_name']
        except (KeyError, IndexError):
            return default
        
    # Leer de un sheets los IDs de los competidores seleccionados a analizar sus precios}
    def scrape_specific_competitors(parametros_sheet, access_token):
        #Definimos el diccionario que va a tener llave: ID Producto y valor: lista de precios de competidores de ese producto
        competitors_price_dict = dict()

        sheet = parametros_sheet.get_worksheet_by_id(1147249681)
        cell_values_delta_precios = sheet.get_all_values()
        sheet_data = pd.DataFrame(cell_values_delta_precios[1:], columns=cell_values_delta_precios[0])
        competidores = sheet_data['Id competidor'].unique().tolist()

        for competidor_user_id in competidores:
            print(competidor_user_id)
            items = get_user_items(competidor_user_id, access_token)
            for item in items:
                print(item['title'])
                # for attribute in item['attributes']:
                #     if attribute['id'] == 'ITEM_CONDITION':
                #         item_condition = attribute['value_name']
                
                if item['catalog_product_id'] is not None and item['condition'] == 'new':
                #     category_id = item['category_id'] #CATEGORIA    
                #     marca = get_attribute(item, 0) #BRAND
                #     linea =  get_attribute(item, 2) #LINE
                #     modelo =  get_attribute(item, 3) #MODEL
                #     # if category_id == 'MLA4980' and marca in ['Kingston','SanDisk'] and linea in ['Cruzer','Datatraveler'] and modelo in ['Blade','Exodia']: #pendrives/memorias
                #         # print('ok producto')
                #     print('Es de catalogo''\n')
                #     print(category_id)
                #     print(linea)
                #     print(modelo)
                #     print('\n')
                # else:
                    product_id = item['id']
                    category_id = item['category_id'] #CATEGORIA
                    marca = get_attribute(item, 0) #BRAND
                    linea =  get_attribute(item, 2) #LINE
                    modelo =  get_attribute(item, 3)
                    if category_id == 'MLA4980' and marca in ['Kingston','SanDisk'] and linea in ['Cruzer','Datatraveler'] and modelo in ['Blade','Exodia']: #pendrives/memorias
                        print('\n''matchea con el nuestro''\n')

                        item_price = item.get('price', None)
                        competitors_price_dict[product_id].append(item_price)

                        #Limpio precios que son outliers
                        cleaned_sample = remove_outliers_zscore(competitors_price_dict[product_id])
                        # Saco el precio promedio de los vendedores de mi articulo que no estan en catalogo
                        price_avg_not_catalog = statistics.mean(cleaned_sample)
                        return price_avg_not_catalog

    def get_publications_by_gtin(lista_productos_propios, token_de_acceso):
        publication_by_sku = dict()
        for item in lista_productos_propios:
            product_id = item['id']     
            try: 
                publication_by_sku[get_product_gtin(token_de_acceso, product_id)].append(product_id)
            except:
                publication_by_sku[get_product_gtin(token_de_acceso, product_id)] = [product_id]
        return publication_by_sku

    def get_publications_by_shipping_conditions(lista_productos_propios, token_de_acceso):
        publications_by_shipping_conditions = dict()
        for item in lista_productos_propios:
            product_id = item['id']     
            item_attributes = get_item_attributes(product_id, token_de_acceso)['shipping']
            # tags = item_attributes['tags']
            local_pick_up = item_attributes['local_pick_up']
            free_shipping = item_attributes['free_shipping']
            logistic_type = item_attributes['logistic_type']
            store_pick_up = item_attributes['store_pick_up']
            try: 
                # publications_by_shipping_conditions[tags].append(product_id)
                publications_by_shipping_conditions[local_pick_up].append(product_id)
                publications_by_shipping_conditions[free_shipping].append(product_id)
                publications_by_shipping_conditions[logistic_type].append(product_id)
                publications_by_shipping_conditions[store_pick_up].append(product_id)
            except:
                publications_by_shipping_conditions[local_pick_up] = product_id
                publications_by_shipping_conditions[free_shipping] = product_id
                publications_by_shipping_conditions[logistic_type] = product_id
                publications_by_shipping_conditions[store_pick_up] = product_id

        return publications_by_shipping_conditions

    def get_publications_by_payment_conditions(lista_productos_propios, token_de_acceso):
        publications_by_payment_conditions = dict()
        for item in lista_productos_propios:
            product_id = item['id']     
            item_attributes = get_item_attributes(product_id, token_de_acceso)
            acepta_mp = item_attributes['accepts_mercadopago']
            non_mp_payment_methods = item_attributes['non_mercado_pago_payment_methods']
            buying_mode = item_attributes['buying_mode']
            try: 
                # publications_by_shipping_conditions[tags].append(product_id)
                publications_by_payment_conditions[acepta_mp].append(product_id)
                publications_by_payment_conditions[non_mp_payment_methods].append(product_id)
                publications_by_payment_conditions[buying_mode].append(product_id)
            except:
                publications_by_payment_conditions[acepta_mp] = product_id
                publications_by_payment_conditions[non_mp_payment_methods] = product_id
                publications_by_payment_conditions[buying_mode] = product_id
        return publications_by_payment_conditions

    def post_promotion(id_publicacion, token_de_acceso, llamados):
        url = f"https://api.mercadolibre.com/seller-promotions/items/{id_publicacion}?app_version=v2"
        payload = "{\r\n  \"promotion_id\": \"C-MLA96853\",\r\n  \"promotion_type\": \"SELLER_CAMPAIGN\"\r\n }"
        headers = {
        'Authorization': 'Bearer ' + token_de_acceso,
        'Content-Type': 'text/plain'
        }
        response = requests.request("POST", url, headers=headers, data=payload)
        return response.json(), llamados

    def post_discount(id_publicacion, token_de_acceso, llamados):
        url = f"https://api.mercadolibre.com/seller-promotions/items/{id_publicacion}"
        payload = 'promotion_id=&offer_id=&promotion_type=PRE_NEGOTIATED'
        headers = {
        'Authorization': 'Bearer ' + token_de_acceso,
        'Content-Type': 'application/x-www-form-urlencoded'}
        response = requests.request("POST", url, headers=headers, data=payload)
        return response.json(), llamados

    def get_promotions(id_publicacion, token_de_acceso, llamados):
        url = f"https://api.mercadolibre.com/seller-promotions/items/{id_publicacion}?channel=marketplace"
        payload = {}
        headers = {'Authorization': 'Bearer ' + token_de_acceso}
        response = requests.request("GET", url, headers=headers, data=payload)
        return response.json(), llamados

    def get_promotion_info(id_promocion, token_de_acceso, llamados):
        url = f"https://api.mercadolibre.com/seller-promotions/promotions/{id_promocion}/items?promotion_type=SELLER_CAMPAIGN&channel=marketplace"
        payload = {}
        headers = {'Authorization': 'Bearer ' + token_de_acceso}
        response = requests.request("GET", url, headers=headers, data=payload)
        return response.json()

    def cantidad_publicaciones_por_categoria(category_id, token_de_acceso):
        url = f"https://api.mercadolibre.com/categories/{category_id}"
        payload = {}
        headers = {'Authorization': 'Bearer ' + token_de_acceso}
        response = requests.request("GET", url, headers=headers, data=payload)
        return response.json().get('total_items_in_this_category', None)

    def get_item_data_by_category(url, token_de_acceso):
        payload = {}
        headers = {'Authorization': 'Bearer ' + token_de_acceso}
        response = requests.request("GET", url, headers=headers, data=payload)
        return response.json()

    def scrapear_por_categoria_y_gtin(category_id, token_de_acceso, lista_productos_propios):
        lista_precios = []

        competitor_prices_by_gtin_dict = dict()
        avg_competitor_prices_by_gtin_dict = dict()

        url = f"https://api.mercadolibre.com/sites/MLA/search?category={category_id}&catalog_product_id=null"
        data = get_item_data_by_category(url, token_de_acceso)
        if data is not None:
            total_results = data.get('paging', {}).get('total', 0)
            items_per_page = data.get('paging', {}).get('limit', 0)
            total_pages = (total_results + items_per_page - 1) // items_per_page
            all_items = data.get('results', [])
            for page in range(1, total_pages):
                offset = page * items_per_page
                next_page_url = f"{url}&offset={offset}"
                page_data = get_item_data_by_category(next_page_url, token_de_acceso)
                if page_data is not None:
                    all_items.extend(page_data.get('results', []))
                else:
                    print(f"Failed to fetch data for page {page}")
        else:
            print("Failed to fetch data for the initial page")
        for item in all_items:
            product_id = item.get('id')
            # print('Product id: ', product_id)
            # print('Gtin: ', get_product_gtin(token_de_acceso, product_id))
            if get_product_gtin(token_de_acceso, product_id) in list(get_publications_by_gtin(lista_productos_propios,token_de_acceso).keys()):
                item_price = item.get('price')
                # print('Price: ', item_price)
                try:
                    competitor_prices_by_gtin_dict[get_product_gtin(token_de_acceso, product_id)].append(item_price)
                except:
                    competitor_prices_by_gtin_dict[get_product_gtin(token_de_acceso, product_id)] = [item_price]
                # print('Price in dict: ', competitor_prices_by_gtin_dict[get_product_gtin(token_de_acceso, product_id)])
        for gtin in list(competitor_prices_by_gtin_dict.keys()):
            try:
                avg_competitor_prices_by_gtin_dict[gtin].append(statistics.mean(competitor_prices_by_gtin_dict[gtin]))
            except:
                avg_competitor_prices_by_gtin_dict[gtin] = statistics.mean(competitor_prices_by_gtin_dict[gtin])
        return avg_competitor_prices_by_gtin_dict

    # Initialize the OpenSearch client
    opensearch_domain = 'https://search-meli-domain-sauo2gxwpq4mm2r2qreopivdw4.us-east-2.es.amazonaws.com:443'

    os_client = OpenSearch(
        hosts=[opensearch_domain],
        http_auth=('coin-custody', 'v!2R16hP%%G6'),
        scheme = "https",
        port = 443
    )

    # Initialize the S3 client
    s3_client = boto3.client('s3')

    google_api_dict_list = []
    google_key_locations = [
        'abettucci/MELIproject/Google_API_JSON_Key_File3',
        'abettucci/MELIproject/Google_API_JSON_Key_File']
    for api_dict in google_key_locations:
        secret_name = api_dict
        region_name = "us-east-2"
        # Create a Secrets Manager client
        sm_session = boto3.session.Session()
        sm_client = sm_session.client(
            service_name='secretsmanager',
            region_name=region_name)
        try:
            get_secret_value_response = sm_client.get_secret_value(
                SecretId=secret_name)
        except ClientError as e:
            raise e
        # Decrypts secret using the associated KMS key.
        secret = get_secret_value_response
        secret_data = json.loads(secret['SecretString'])
        key_dict = {
            "private_key_id" : secret_data.get('private_key_id'),
            "type" : secret_data.get('type'),
            "project_id" : secret_data.get('project_id'),
            "client_id" : secret_data.get('client_id'),
            "client_email" : secret_data.get('client_email'),
            "private_key" : secret_data.get('private_key')
        }
        google_api_dict_list.append(key_dict)

    # Leemos el Google Sheets que contiene los ultimos tokens para renovarlos o volver a utilizarlos
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        google_api_dict_list[0], 
        ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive'])
    gc = gspread.authorize(creds) 

    api_key = google_api_dict_list[0]["private_key_id"]
    sh = gc.open_by_key('1AbwRrOEFrcCXR2v8_djqckhLjJOM_2r8S1VwBwhS5Q0') #es un excel propio
    
    # Excel con tokens de auth
    worksheet_tokens_mio = make_read_api_call('get_worksheet_by_id',1387040377,sh,'','', google_api_dict_list)
    
    # Excels de parametros
    parametros_sheet = gc.open_by_key('1jPmF5waE7A4dQsPhrM18mgyCc-Pmesy-qou_2MinO5s')
    data_parametros_sheet = make_read_api_call('get_worksheet_by_id_and_get_all_values',0,parametros_sheet,0,'', google_api_dict_list)

    # Hoja de delta precios
    columnas_delta_precios = data_parametros_sheet[0][6:] #HEADERS
    data_parametros_sheet = data_parametros_sheet[1:6] #ROWS
    filas_delta_precios = [[row[i] for i in range(6, len(row))] for row in data_parametros_sheet]
    df_delta_precios = pd.DataFrame(filas_delta_precios, columns = columnas_delta_precios)

    # Hoja de tiempos
    filas = data_parametros_sheet[1:2][0][:6]
    columnas = data_parametros_sheet[0][:6]
    df_tiempos_minimos = pd.DataFrame([filas], columns=columnas)
    df_horarios = tiempos_minimos(df_tiempos_minimos)

    fila = 0
    for fila in range(2,4):
        refresh_token = worksheet_tokens_mio.cell(fila, 1).value  
        access_token = worksheet_tokens_mio.cell(fila, 2).value  
        t_expiracion = worksheet_tokens_mio.cell(fila, 3).value 
        app_id = worksheet_tokens_mio.cell(fila, 6).value 
        secret_client_id = worksheet_tokens_mio.cell(fila, 7).value 
        log_spreadsheet = worksheet_tokens_mio.cell(fila, 8).value 
        cuenta_meli = get_user_id(access_token).get('nickname',None)
        print('Cuenta: ', cuenta_meli)

        # Obtenemos la hora actual para evaluar si se supero el horario de expiracion de los tokens de la API de MELI
        buenos_aires_timezone = pytz.timezone('America/Argentina/Buenos_Aires')
        current_time = datetime.now(buenos_aires_timezone).strftime('%Y-%m-%d %H:%M:%S')
        current_time = datetime.strptime(current_time, '%Y-%m-%d %H:%M:%S')
        t_expiracion = datetime.strptime(t_expiracion, '%m/%d/%Y %H:%M:%S')

        # Si todavia no se expiraron los tokens para pinguear la API de MercadoLibre, seguimos utilizando el ultimo token
        if current_time < t_expiracion:
            token_de_acceso = access_token
        else:
            # Generamos un nuevo refresh_token y acces_token con el get_Access_token() para renovar los tokens de la API de MELI
            proximo_refresh_token, token_de_acceso,tiempo_de_expiracion = get_access_token(app_id, secret_client_id, refresh_token)

            # Hacemos un overwrite en el Sheets para reemplazar el refresh_token, access_token y fecha de exp viejos
            horario_expiracion_refresh_token = current_time + timedelta(seconds=tiempo_de_expiracion) #'expires in' = 21600 seg = 6 hs 
            horario_expiracion_refresh_token = horario_expiracion_refresh_token.strftime('%m/%d/%Y %H:%M:%S')
            horario_expiracion_refresh_token = horario_expiracion_refresh_token.replace(' ', ' 0', 1) if horario_expiracion_refresh_token[11] == ' ' else horario_expiracion_refresh_token

            worksheet_tokens_mio.update_cell(fila, 1, proximo_refresh_token)
            worksheet_tokens_mio.update_cell(fila, 2, token_de_acceso)
            worksheet_tokens_mio.update_cell(fila, 3, str(horario_expiracion_refresh_token))

        # Hoja de logs
        log_sheet = gc.open_by_key(log_spreadsheet)

        #Si hay productos nuevos agrego hojas en el log sheet
        worksheet_names = []
        worksheet_list = log_sheet.worksheets()
        for worksheet in worksheet_list[1:]:
            worksheet_names.append(worksheet.title)

        for index,row in df_delta_precios.iterrows():
            sheet_name = row['Descripcion']
            if sheet_name not in worksheet_names:
                existing_worksheet = worksheet_list[1] #agarro de template la primera publicacion del log sheets 
                new_worksheet = existing_worksheet.duplicate(new_sheet_name=sheet_name, insert_sheet_index=1) #duplico la hoja de template y la renombro con el nombre de la nueva publicacion
                all_values = new_worksheet.get_all_values()
                header_row = all_values[0] # me guardo los encabezados
                new_worksheet.clear()
                cell_list = new_worksheet.range('A1:' + gspread.utils.rowcol_to_a1(1, len(header_row)))
                for i, value in enumerate(header_row):
                    cell_list[i].value = value
                new_worksheet.update_cells(cell_list) # pego los encabezados

        # Leemos las promos activas/a activar en el Google Spreadsheet "parametros_algoritmo"
        data_promociones = make_read_api_call('get_worksheet_by_id_and_get_all_values',671120957,parametros_sheet,0,'', google_api_dict_list)

        # No agregar varias promos para una misma publicacion, sobreescribir, o sea modificar la fila y no agregar filas extras
        columnas_df_promociones = data_promociones[0][:8] #HEADERS
        data_df_promociones = data_promociones[1:len(data_promociones) + 1] #ROWS
        filas_df_promociones = [[row[i] for i in range(0, len(row))] for row in data_df_promociones]
        df_promociones = pd.DataFrame(filas_df_promociones, columns = columnas_df_promociones)
        promos_activas = df_promociones.loc[df_promociones['Activo']=='1']
        # print(df_promociones)

        # Obtenemos el id de usuario y los items publicados del cliente
        my_user = get_user_id(token_de_acceso)
        my_user_id = my_user.get('id',None)
        lista_productos_propios = get_user_items(my_user_id, token_de_acceso)

        # put_price_update(worksheet_tokens_mio, df_promociones, 'MLA1388324258', 100, token_de_acceso)

        # Iteramos sobre los productos en venta del cliente
        for producto in lista_productos_propios:
            # Leemos solo los productos que son de catalogo
            if producto.get('catalog_product_id') is None:
                # my_product_id = producto['id']
                category_id = producto['category_id']
                print(list(get_publications_by_gtin(lista_productos_propios,token_de_acceso).keys()))
                
                avg_competitor_prices_by_gtin_dict = scrapear_por_categoria_y_gtin(category_id, token_de_acceso, lista_productos_propios)
                for k,v in avg_competitor_prices_by_gtin_dict.items():
                    print(k,v)

                # start_time = time.time()

                # ## Campos del log
                # id_publicacion = producto.get('id', None),
                # nombre_publicacion = producto.get('title',None),
                # link_publicacion = producto.get('permalink', None),
                # precio_item_mio = producto.get('price', None),
                # precio_minimo = precio_item_mio,
                # precio_inicial = precio_item_mio,
                # ping_date = iso_date_string = datetime.utcnow().isoformat(),
                # last_updated_dt = ping_date,
                # posicion_en_catalogo = 1,
                # accion = 'precio a ganar 10000',
                # precio_ganador = precio_item_mio,
                # runtime = round(time.time() - start_time,2), 
                # meli_Api_calls = 1,
                # llamados_write_API_google = 1,
                # llamados_read_API_google = 1,
                # llamados_API_google = 1,
                # time_difference = '',
                # id_ganador = producto.get('seller', []).get('id', None),
                # nickname_ganador = producto.get('seller', []).get('nickname', None),
                # stock_vendedor = producto.get('available_quantity', None),
                # unidades_vendidas_ganador = producto.get('seller', [])['seller_reputation']['transactions']['completed'],
                # free_shipping_ganador = producto.get('shipping', [])['free_shipping'],
                # logistic_type_ganador = producto.get('shipping', [])['logistic_type'],
                # store_pick_up_ganador = producto.get('shipping', [])['store_pick_up'],
                # ciudad_vendedor = producto.get('seller_address', [])['city']['name']
                # claims_vendedor = 0
                # delayed_handling_time_vendedor = 0
                # cancellations_vendedor = 0
                # claims_vendedor = producto.get('seller_reputation', [])['claims']['value'],
                # sales_vendedor = unidades_vendidas_ganador,
                # delayed_handling_time_vendedor = producto.get('seller_reputation', [])['delayed_handling_time']['value']
                # cancellations_vendedor = producto.get('seller_reputation', [])['cancellations']['value']

                # write_log_and_save_in_s3(
                #         cuenta_meli,
                #         id_publicacion, 
                #         nombre_publicacion,
                #         link_publicacion,
                #         precio_minimo,
                #         precio_inicial,
                #         precio_item_mio,
                #         ping_date,
                #         last_updated_dt,
                #         posicion_en_catalogo,
                #         accion,
                #         precio_ganador,
                #         runtime,
                #         meli_Api_calls,
                #         llamados_write_API_google, 
                #         llamados_read_API_google,
                #         llamados_API_google,
                #         time_difference,
                #         str(id_ganador),
                #         nickname_ganador,
                #         stock_vendedor,
                #         unidades_vendidas_ganador,
                #         free_shipping_ganador,
                #         logistic_type_ganador,
                #         store_pick_up_ganador,
                #         ciudad_vendedor,
                #         claims_vendedor,
                #         sales_vendedor,
                #         delayed_handling_time_vendedor,
                #         cancellations_vendedor
                #     )
                
                # index_and_transfer_from_s3_to_ecr()

        # scrape_specific_competitors(parametros_sheet, access_token)
        # print(get_publications_by_gtin(lista_productos_propios, token_de_acceso))

        # print(get_publications_by_payment_conditions(lista_productos_propios, token_de_acceso))

        # log = put_price_update(my_product_id, my_min_price, token_de_acceso)
                

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "hello world",
            }
        ),
    }
