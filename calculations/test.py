from fastapi import FastAPI, Header, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
from datetime import date
import traceback
import pandas as pd
import uuid
import csv
import os
import math

api = FastAPI()

#Key Assumptions based on EcoLogits Paper
ALPHA      = 1.17e-6
BETA       = -1.12e-2
GAMMA      = 4.05e-5
BATCH_SIZE = 64
P_ACTIVE_B = 300 #97
P_TOTAL_B  = 900 #45
Q_BITS     = 16
M_GPU_GB   = 80
GPU_INSTALLED = 8
#https://artificialanalysis.ai/leaderboards/providers
TOKENS_PER_SECOND = 66
miles_per_kg_of_co2 = 3.79

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
GLOBAL_AVERAGE_FEM = 436.0
US_COUNTRY_KEYS    = {"United States"}

#https://files.ember-energy.org/public-downloads/ember_subnational_data_methodology.pdf
carbon_intensity_path =  os.path.join(BASE_DIR, "input_data", "carbon_intensity.csv")
carbon_intensity = pd.read_csv(carbon_intensity_path)

#Water consumption datasets
#https://www.epa.gov/system/files/documents/2025-06/summary_tables_rev2.xlsx
usa_grid_path = os.path.join(BASE_DIR, "input_data", "usa_energy_grid_mix.csv")
usa_energy_grid_mix = pd.read_csv(usa_grid_path)
#https://ember-energy.org/data/yearly-electricity-data/
global_grid_path = os.path.join(BASE_DIR, "input_data", "clean_energy_grid_international.csv")
international_energy_grid_mix = pd.read_csv(global_grid_path)
#https://apps.rec-cer.gc.ca/ftrppndc/dflt.aspx?GoCTemplateCulture=en-CA
canada_grid_path = os.path.join(BASE_DIR, "input_data", "clean_canada_energy_grid.csv")
canada_energy_grid_mix = pd.read_csv(canada_grid_path)
#electricity water intensity factor - https://doi.org/10.1016/j.rser.2019.109391
ewif_path = os.path.join(BASE_DIR, "input_data", "electricity_generation_water_intensity.csv")
ewif = pd.read_csv(ewif_path)
# https://github.com/wri/Aqueduct40, https://www.wri.org/applications/aqueduct/water-risk-atlas/#/?advanced=false&basemap=hydro&indicator=w_awr_def_tot_cat&lat=30&lng=-80&mapMode=view&month=1&opacity=0.5&ponderation=DEF&predefined=false&projection=absolute&scenario=optimistic&scope=baseline&threshold&timeScale=annual&year=baseline&zoom=3 
future_water_stress_path = os.path.join(BASE_DIR, "input_data", "watershed_future_annual_CanUS.csv")
future_water_stress = pd.read_csv(future_water_stress_path)
baseline_water_stress_path = os.path.join(BASE_DIR, "input_data", "watershed_baseline_annual_CanUS.csv")
baseline_water_stress = pd.read_csv(baseline_water_stress_path)
countries_region_path = os.path.join(BASE_DIR, "input_data", "countries_by_region.csv")
countries_by_region = pd.read_csv(countries_region_path)
us_state_to_abbrev = { #https://gist.github.com/rogerallen/1583593
	"Alabama": "AL",
	"Alaska": "AK",
	"Arizona": "AZ",
	"Arkansas": "AR",
	"California": "CA",
	"Colorado": "CO",
	"Connecticut": "CT",
	"Delaware": "DE",
	"Florida": "FL",
	"Georgia": "GA",
	"Hawaii": "HI",
	"Idaho": "ID",
	"Illinois": "IL",
	"Indiana": "IN",
	"Iowa": "IA",
	"Kansas": "KS",
	"Kentucky": "KY",
	"Louisiana": "LA",
	"Maine": "ME",
	"Maryland": "MD",
	"Massachusetts": "MA",
	"Michigan": "MI",
	"Minnesota": "MN",
	"Mississippi": "MS",
	"Missouri": "MO",
	"Montana": "MT",
	"Nebraska": "NE",
	"Nevada": "NV",
	"New Hampshire": "NH",
	"New Jersey": "NJ",
	"New Mexico": "NM",
	"New York": "NY",
	"North Carolina": "NC",
	"North Dakota": "ND",
	"Ohio": "OH",
	"Oklahoma": "OK",
	"Oregon": "OR",
	"Pennsylvania": "PA",
	"Rhode Island": "RI",
	"South Carolina": "SC",
	"South Dakota": "SD",
	"Tennessee": "TN",
	"Texas": "TX",
	"Utah": "UT",
	"Vermont": "VT",
	"Virginia": "VA",
	"Washington": "WA",
	"West Virginia": "WV",
	"Wisconsin": "WI",
	"Wyoming": "WY",
	"District of Columbia": "DC",
	"American Samoa": "AS",
	"Guam": "GU",
	"Northern Mariana Islands": "MP",
	"Puerto Rico": "PR",
	"United States Minor Outlying Islands": "UM",
	"Virgin Islands, U.S.": "VI",
}
#https://datacenters.microsoft.com/sustainability/efficiency/ for PUE and WUE_onsite
PUEs = {
	"Americas":1.16,
	"Global": 1.17,
	"Asia_Pacific": 1.28,
	"Europe_Middle_East_and_Africa": 1.16
}
WUE_onsite = {
	"Americas":0.34,
	"Global": 0.27,
	"Asia_Pacific": 0.25,
	"Europe_Middle_East_and_Africa": 0.03
}

#Constant calculations
#total energy consumed by a single GPU over a request period (Wh)
def _compute_gpu_count(p_total_b: float, q_bits: int, m_gpu_gb: float) -> int:
	m_model_gb = 1.2 * (p_total_b * 1e9 * q_bits) / 8 / 1e9
	ceil_ratio = math.ceil(m_model_gb/ m_gpu_gb)
	return 2 ** math.ceil(math.log2(ceil_ratio))

#returns a value for energy consumed per token (Wh/token)
def _compute_per_token_coeff(alpha: float, beta: float, gamma: float, batch_size: int, p_active_b: float) -> float:
	return alpha * math.exp(beta * batch_size) * p_active_b + gamma

GPU_COUNT       = _compute_gpu_count(P_TOTAL_B, Q_BITS, M_GPU_GB)
PER_TOKEN_COEFF = _compute_per_token_coeff(ALPHA, BETA, GAMMA, BATCH_SIZE, P_ACTIVE_B)

def parse_location_string(location: str) -> dict:
	# Split by comma and strip whitespace
	parts = [p.strip() for p in location.split(',')]
	# Map parts to keys based on their position
	return {
		"country": parts[0] if len(parts) > 0 else None,
		"state": parts[1] if len(parts) > 1 else None,
		"watershed_id": parts[2] if len(parts) > 2 else None
	}

def compute_WUE_offsite(energy: int, energy_grid_mix: pd, country: str) -> float:
	#calculating numerator of wue_off
	numerator = 0
	if(country == "United States"):
		#loop through the columns of energy grid that contain percentages for each fuel type
		for fuel_type_percent in energy_grid_mix.iloc[:, 4:14].columns:
			if fuel_type_percent == 'OtherFossilPercent' or fuel_type_percent == 'OtherUnknownPercent': #how should we deal with these?
				continue
			#rename to match rows of ewif
			fuel_type = fuel_type_percent.replace('Percent', '') 
			water_intensity = ewif[(ewif['PowerType'] == fuel_type) & (ewif['Key'] == 'Average')]['WaterConsumption_L_per_kWh'].iloc[0] #should we use average or high/low?
			numerator += (energy_grid_mix[fuel_type_percent].iloc[0] * energy * water_intensity)
	elif(country == "Canada"):
		for fuel_type_percent in energy_grid_mix.iloc[:,11:17]:
			#rename to match rows of ewif
			fuel_type = fuel_type_percent.replace('Percent', '')
			water_intensity = ewif[(ewif['PowerType'] == fuel_type) & (ewif['Key'] == 'Average')]['WaterConsumption_L_per_kWh'].iloc[0]
			numerator += (energy_grid_mix[fuel_type_percent].iloc[0] * energy * water_intensity)
	else:
		#loop through the columns of energy grid that contain percentages for each fuel type
		for fuel_type_percent in energy_grid_mix.iloc[:,5:13].columns:
			if fuel_type_percent == "Other Fossil" or fuel_type_percent == "Other Renewables":
				continue
			water_intensity = ewif[(ewif['PowerType'] == fuel_type_percent) & (ewif['Key'] == 'Average')]['WaterConsumption_L_per_kWh'].iloc[0] #should we use average or high/low?
			numerator += (energy_grid_mix[fuel_type_percent].iloc[0] * energy * water_intensity)
	WUE_off = numerator / energy
	print("WUE_off = " + str(WUE_off))
	return WUE_off

#calculate gallons consumed for given kwh in the given location
def kwh_to_ml(kwh: float, location_string: str) ->float:
	location = parse_location_string(location_string)
	#find PUE and WUE_onsite for given location
	if countries_by_region.loc[countries_by_region['Country'] == location["country"], 'Region'].iloc[0] == "Americas":
		PUE = PUEs["Americas"]
		WUE_on = WUE_onsite["Americas"]
	elif countries_by_region[countries_by_region['Country'] == location["country"]]['Region'].values[0] == "Asia-Pacific":
		PUE = PUEs["Asia_Pacific"]
		WUE_on = WUE_onsite["Asia_Pacific"]
	elif countries_by_region[countries_by_region['Country'] == location["country"]]['Region'].values[0] == "EMEA":
		PUE = PUEs["Europe_Middle_East_and_Africa"]
		WUE_on = WUE_onsite["Europe_Middle_East_and_Africa"]
	else:
		PUE = PUEs["Global"]
		WUE_on = WUE_onsite["Global"]
	#Find the electricity grid makeup
	if location["country"] == "United States":
		state_abbr = us_state_to_abbrev[location["state"]]
		#the row in usa_energy_grid_mix for our current state
		current_energy_grid_mix = usa_energy_grid_mix[usa_energy_grid_mix['State'] == state_abbr]
	elif location["country"] == "Canada":
		current_energy_grid_mix = canada_energy_grid_mix[canada_energy_grid_mix['Province'] == location['state']]
	elif location["country"] in international_energy_grid_mix['Area'].values: #don't have global values yet
		current_energy_grid_mix = international_energy_grid_mix[international_energy_grid_mix['Area'] == location["country"]] 
	else:
		print("Country not found in energy grid mix: " + location["country"])
		return 0.0
	#calculate WUE_offsite
	WUE_off = compute_WUE_offsite(kwh, current_energy_grid_mix, location["country"])
	total_water_consumption = kwh * (WUE_on + PUE * WUE_off)
	#liters to milliliters conversion
	total_ml_consumed =  total_water_consumption * 1000
	return total_ml_consumed

def calculate_AWI(string_id:str, water_l: float, location:str):
    #calculates Adjusted Water Impact using (Wu et al. 2025) methods
    #input: Aqueduct watershed string id, water consumed L, location string
    #returns awi_dict (containing keys: short awi, long awi 10, long awi 1, location string)
    awi_dict = {}
    #recorded baseline (2019) water stress for given watershed string id
    current_baseline = baseline_water_stress[baseline_water_stress['string_id'] == string_id]
    if current_baseline.empty:
        return None

    wsf_short = float(current_baseline['bws_raw'].iloc[0])
    awi_dict["short_awi"] = water_l * wsf_short

    # calculating long term AWI
    pfafid = int([p.strip() for p in string_id.split('-')][0])
    current_future_df = future_water_stress[future_water_stress['pfaf_id'] == pfafid]
    future_ws = {
        2019: wsf_short,
        #business as usual projected raw water stress for 2030
        2030: float(current_future_df['bau30_ws_x_r'].iloc[0]),
        2050: float(current_future_df['bau50_ws_x_r'].iloc[0]),
        2080: float(current_future_df['bau80_ws_x_r'].iloc[0])
    }
    T_years = [2019, 2030, 2050, 2080]
    gammas = [0.1, 0.01] #discount rates
    for gamma in gammas:
        w_t_prime = 0
        wsf_long = 0
        for t in T_years:
            w_t_prime += 1 / (1+gamma)**(t-2019)
        for t in T_years:
            w_t = (1 / (1+gamma)**(t-2019)) / w_t_prime
            wsf_long += w_t * future_ws[t]
        gamma_string = str(int(gamma*100))
        awi_dict[f"long_awi_{gamma_string}"] = water_l * wsf_long

    awi_dict['location'] = location
    return awi_dict #short_awi, long_awi_10, long_awi_1, location string

def get_AWI(emissions):
    # gets Adjusted Water Impact values for each location in emissions.csv - and scales up
    # collected data for Haverford College
    # returns dict: 'Country, State, Aqueduct Watershed ID': AWI_short, AWI_long0.1, AWI_long0.01

    # create new dataframe that holds total water consumption by unique location and
    # number of users
    location_based_emissions = emissions.groupby('location').agg(
        total_ml=('water_ml', 'sum'),
        unique_users=('user_id', 'nunique')
        ).reset_index()
    # milliliters to liters
    location_based_emissions['water_L'] = location_based_emissions['total_ml'] / 1000 #* 3.785

    string_ids = {} #watershed string id: full location string
    awis = {} #watershed string id: dict (short awi, long awi 10, long awi 1, ['full location'])
    pfaf_water = {} #watershed string id: water L
    for index,row in location_based_emissions.iterrows(): #only calculating for US
        if "United States" not in row["location"] and "Canada" not in row["location"]:
            continue
        location_dict = parse_location_string(row["location"])
        stringid = str(location_dict['watershed_id'])
        if stringid == "None":
            continue
        if stringid not in string_ids:
            string_ids[stringid] = [row['location']]
            pfaf_water[stringid] = row['water_L']
        else:
            string_ids[stringid].append(row['location'])
            pfaf_water[stringid] += row['water_L']

    for stringid in string_ids:
        #scale up data to haverford college over an academic year
        if "731506-USA.39_1-1400" == stringid:
            current_unique_users = 0
            for location in string_ids[stringid]:
                current_unique_users += location_based_emissions[location_based_emissions['location'] == location]['unique_users'].item()
            scaled_water = (pfaf_water[stringid] / current_unique_users) * 231 * 1479
            awis[f"{stringid}_scaled"] = calculate_AWI(stringid, scaled_water, string_ids[stringid])
        #calculate AWIs for current stringid
        awis[stringid] = calculate_AWI(stringid, pfaf_water[stringid], string_ids[stringid])
    return awis

def awis_to_csv(awis_dict:dict, filename:str):
    print("awis_to_csv called")
    # filter out any None values
    cleaned_dict = {k: v for k, v in awis_dict.items() if v is not None}

    # if the entire dictionary is empty after filtering, create an empty file
    if not cleaned_dict:
        df = pd.DataFrame(columns=['pfafid', 'short_awi', 'long_awi_10', 'long_awi_1', 'location'])
        df.to_csv(f"{filename}.csv", index=False)
        return

    # convert the clean, filtered dictionary to a DataFrame
    df = pd.DataFrame.from_dict(cleaned_dict, orient='index')

    # move the ID from the index to a proper column
    df.index.name = 'pfafid'
    df = df.reset_index()

    # clean up the location list
    if 'location' in df.columns:
        df['location'] = df['location'].apply(lambda x: '; '.join(x) if isinstance(x, list) else x)

    print("Writing:", f"{filename}.csv")
    # save to csv
    df.to_csv(f"{filename}.csv", index=False, mode='w')

#COUNTRY_FEM, STATE_FEM = _load_fem_tables()

def parse_location(location: str) -> tuple:
    parts = [p.strip() for p in location.split(",")] if location else []
    parts += [None] * (3 - len(parts))
    return tuple(parts[:3])

#returns the carbon intensity (F_em in gCO2eq/kWh) of the given location
def get_fem(location: str) -> float:
        location_dict = parse_location_string(location)
        fem = 0
        if location_dict["country"] == "United States":
                state_abbr = us_state_to_abbrev[location_dict["state"]]
                current_energy_grid_mix = usa_energy_grid_mix[usa_energy_grid_mix['State'] == state_abbr]
                for index, row in carbon_intensity.iterrows():
                        fuel_type = f"{row.iloc[0].strip()}Percent"
                        fem += row.iloc[1] * current_energy_grid_mix[fuel_type].iloc[0]

        elif location_dict["country"] == "Canada":
                current_energy_grid_mix = canada_energy_grid_mix[canada_energy_grid_mix['Province'] == location_dict['state']]
                for index, row in carbon_intensity.iterrows():
                        if row.iloc[0] == "Nuclear" or row.iloc[0] == "Geothermal":
                               continue
                        fuel_type = f"{row.iloc[0].strip()}Percent"
                        fem += row.iloc[1] * current_energy_grid_mix[fuel_type].iloc[0]

        elif location_dict["country"] in international_energy_grid_mix['Area'].values:
                current_energy_grid_mix = international_energy_grid_mix[international_energy_grid_mix['Area'] == location_dict["country"]] 
                for fuel_type_percent in current_energy_grid_mix.iloc[:,5:13].columns:
                    if fuel_type_percent == "Other Fossil" or fuel_type_percent == "Other Renewables":
                        continue
                    c_i = carbon_intensity[(carbon_intensity['PowerType'] == fuel_type_percent)]['carbon_intensity_g_kwh'].iloc[0]
                    fem += (current_energy_grid_mix[fuel_type_percent].iloc[0] * c_i)
        else:
                print("Country not found in energy grid mix: " + location_dict["country"])
                print(international_energy_grid_mix['Area'])
                return

        return fem

def get_PUE(location: str) -> float:
        location = parse_location_string(location)
        #find PUE for given location
        if countries_by_region.loc[countries_by_region['Country'] == location["country"], 'Region'].iloc[0] == "Americas":
                PUE = PUEs["Americas"]
        elif countries_by_region[countries_by_region['Country'] == location["country"]]['Region'].values[0] == "Asia-Pacific":
                PUE = PUEs["Asia_Pacific"]
        elif countries_by_region[countries_by_region['Country'] == location["country"]]['Region'].values[0] == "EMEA":
                PUE = PUEs["Europe_Middle_East_and_Africa"]
        else:
                PUE = PUEs["Global"]
        return PUE

#returns the energy consumed by server without the GPUs (Wh)
def _compute_e_server_gpu(latency):
        kws = latency * 1.2 * (GPU_COUNT / GPU_INSTALLED) * (1 / BATCH_SIZE)
        return kws * 1000/ 3600

#returns the latency (s) (the time it takes the model to respond to an inference)
def _compute_latency(tokens_out: int):
        f_L = 6.78e-4 * P_ACTIVE_B + 3.12e-4 * BATCH_SIZE + 1.94e-2
        return min(tokens_out * f_L, tokens_out / TOKENS_PER_SECOND)

def calculate_kwh(tokens_out: int, PUE: float) -> float:
	latency = _compute_latency(tokens_out)
	e_server_gpu = _compute_e_server_gpu(latency)
	e_gpu     = tokens_out * PER_TOKEN_COEFF
	e_server  = e_server_gpu + GPU_COUNT * e_gpu
	e_request = e_server   * PUE
	return e_request / 1000

def calculate_carbon(e_request: float, fem_gco2_per_kwh: float) -> float:
	co2_g   = (e_request  * fem_gco2_per_kwh)
	return co2_g


FIELDNAMES = ["user_id", "tokens", "location", "date", "fem_gco2_per_kwh", "carbon_g", "kwh", "water_ml", "country", "state", "watershed", "state_code"]

def backfill_carbon(path: str) -> None:
        df = pd.read_csv(path)
        if "kwh" not in df.columns:
          df["kwh"] = df.apply(
            lambda row: calculate_kwh(row["tokens"], get_PUE(row["location"])),
            axis=1
          )
        kwh_needs_calc = df["kwh"].isna() | (df["kwh"].astype(str).str.strip() == "")
        if kwh_needs_calc.any():
                df.loc[kwh_needs_calc, "kwh"] = df.loc[kwh_needs_calc].apply(lambda r: calculate_kwh(r["tokens"],get_PUE(r["location"])),axis=1)
        for col in ("fem_gco2_per_kwh", "carbon_g"):
                if col not in df.columns:
                        df[col] = None
        needs_calc = df["carbon_g"].isna() | (df["carbon_g"].astype(str).str.strip() == "")
        if needs_calc.any():
                df.loc[needs_calc, "fem_gco2_per_kwh"] = (df.loc[needs_calc, "location"].apply(get_fem))
                df.loc[needs_calc, "carbon_g"] = df.loc[needs_calc].apply(lambda r: calculate_carbon(float(r["kwh"]), float(r["fem_gco2_per_kwh"])),axis=1,)
        df[FIELDNAMES].to_csv(path, index=False)

def backfill_water(path: str) -> None:
        df = pd.read_csv(path)
        if "kwh" not in df.columns:
          df["kwh"] = df.apply(
            lambda row: calculate_kwh(row["tokens"], get_PUE(row["location"])),
            axis=1
          )
        if "water_ml" not in df.columns:
               df["water_ml"] = None
        needs_calc = df["water_ml"].isna() | (df["water_ml"].astype(str).str.strip() == "")
        if needs_calc.any():
                df.loc[needs_calc, "water_ml"] = df.loc[needs_calc].apply(lambda r: kwh_to_ml(float(r["kwh"]), str(r["location"])),axis=1,)
        df[FIELDNAMES].to_csv(path, index=False)

def backfill_locations(path:str) -> None:
	df = pd.read_csv(path)
	for col in ['country', 'state', 'watershed', 'state_code']:
        	if col not in df.columns:
           		df[col] = None
	needs_calc = df["country"].isna() | (df["country"].astype(str).str.strip() == "")
	if needs_calc.any():
		split_data = df['location'].str.split(',', expand=True)
		split_data = split_data.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
		df.loc[needs_calc,'country'] = split_data[0] if 0 in split_data.columns else None
		df.loc[needs_calc, 'state'] = split_data[1] if 1 in split_data.columns else None
		df.loc[needs_calc,'watershed'] = split_data[2] if 2 in split_data.columns else None
		df.loc[needs_calc, 'state_code'] = df.loc[needs_calc, 'state'].map(
         	   lambda x: us_state_to_abbrev.get(x, None) if pd.notnull(x) else None
        	)
	df[FIELDNAMES].to_csv(path, index=False)

API_KEY = "44cf2d37-1e0d-4847-b6e9-81bb877bc2d1" #"dev_key_change_me"

api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class EmissionEvent(BaseModel):
    tokens: int
    location: str
    date: str

class CSVRequest(BaseModel):
    data: List[EmissionEvent]
    file_name: str
    user_id: Optional[str] = None

class ReadRequest(BaseModel):
    user_id: str
    file_name: str = "impacts.csv"

class ImgEvent(BaseModel):
    height: int
    width: int
    location: str
    date: str

class ImgCSVRequest(BaseModel):
    data: List[ImgEvent]
    file_name: str
    user_id: Optional[str] = None

@api.post("/data2")
def add_data(event: EmissionEvent, x_api_key: str = Header(default="")):
    #if x_api_key != API_KEY:
        #raise HTTPException(status_code=401, detail="Invalid API key")

    emission.append(event)
    return {"ok": True, "count": len(emission)}

def home():
    return{"message": "Hello World!"}

@api.post("/upload-csv2/")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed.")

    contents = await file.read()

    # Optional: store uploads in a folder
    os.makedirs("uploads", exist_ok=True)
    safe_path = os.path.join("uploads", os.path.basename(file.filename))

    with open(safe_path, "wb") as f:
        f.write(contents)

    return {"message": "CSV file uploaded successfully.", "saved_as": safe_path}


# Read a CSV file and return as JSON
@api.get("/read-csv2/")
async def read_csv(file_name: str):
    try:
        with open(file_name, "r", newline="") as f:
            reader = csv.DictReader(f)
        return [row for row in reader]
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found.")

@api.post("/write-csv-img/")
async def write_csv_img(req: ImgCSVRequest, x_api_key: str = Header(default="")):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    user_id = req.user_id if req.user_id else str(uuid.uuid4())
    os.makedirs("output_data", exist_ok=True)
    path = os.path.join("output_data", os.path.basename(req.file_name))
    with open(path, "a", newline="") as f:
        #add in calculations for images

        df = pd.read_csv(path)

        df["date"] = pd.to_datetime(df["date"])
        df["carbon_g"] = pd.to_numeric(df["carbon_g"], errors="coerce")

        user_df = df[df["user_id"] == user_id].copy()
        if user_df.empty:
              return {"message": "JSON data appended to CSV file succesfully.", "file": path, "request_id": user_id,
                        "user_data": "Welcome to AI Impact Tracker!"}
        total_tokens    = int(user_df["tokens"].sum())
        total_carbon_g = float(user_df["carbon_g"].sum())
        first_date       = user_df["date"].min().date()
        days_since_start = (date.today() - first_date).days + 1
        avg_tokens_per_day = total_tokens    / days_since_start
        avg_carbon_per_day = total_carbon_g / days_since_start
        miles_driven = total_carbon_g * miles_per_kg_of_co2 /1000
        total_ml = float(user_df["water_ml"].sum())
        avg_ml_per_day = total_ml / days_since_start
        total_water_bottles = total_ml / 500
        total_kwh = float(user_df["kwh"].sum())
        avg_kwh = total_kwh / days_since_start
        return {
               "message":    "JSON data appended to CSV file successfully.",
               "file":       path,
               "request_id": user_id,
               "user_data": (
               f"Welcome to AI Impact Tracker! | "
               f"Total tokens: {total_tokens} | "
               f"Daily avg tokens: {avg_tokens_per_day:.0f} | "
               f"Total Carbon Emission: {total_carbon_g:.2f} g CO2 | "
               f"Daily avg carbon: {avg_carbon_per_day:.2f} g CO2 | "
               f"Total Miles Driven: {miles_driven:.2f} miles  | "
               f"Total Water Consumed: {total_ml:.2f} mL | "
               f"Daily avg water:  {avg_ml_per_day:.2f} mL | "
               f"Total Water Bottles: {total_water_bottles:.2f} | "
               f"Total Energy: {total_kwh:.2f} kWh | "
               f"Daily avg energy: {avg_kwh:.2f} kWh"
               ),
        }


@api.post("/write-csv2/")
async def write_csv(req: CSVRequest, x_api_key: str = Header(default="")):
    print(f"Received key: '{x_api_key}'")
    print(f"Expected key: '{API_KEY}'")
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    user_id = req.user_id if req.user_id else str(uuid.uuid4())
    os.makedirs("output_data", exist_ok=True)
    path = os.path.join("output_data", os.path.basename(req.file_name))
    if os.path.exists(path):
        backfill_carbon(path)
        backfill_water(path)
        backfill_locations(path)

    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)

        # If file is empty, write header once
        if f.tell() == 0:
            writer.writeheader()

        for item in req.data:
            fem    = get_fem(item.location)
            pue    = get_PUE(item.location)
            kwh    = calculate_kwh(item.tokens, pue)
            co2_g = calculate_carbon(kwh, fem)
            water_ml = kwh_to_ml(kwh, item.location)
            location_dict = parse_location_string(item.location)
            state_name = location_dict['state']
            state_code = us_state_to_abbrev.get(state_name, None) if state_name else None
            writer.writerow({
		"user_id": user_id,
		"tokens": item.tokens,
		"location": item.location,
		"date": item.date,
                "fem_gco2_per_kwh": fem,
                "carbon_g":        co2_g,
                "water_ml": water_ml,
                "kwh": kwh,
                "country":location_dict['country'],
                "state":location_dict['state'],
                "watershed":location_dict['watershed_id'],
                "state_code":state_code,
		})
        df = pd.read_csv(path)

        df["date"] = pd.to_datetime(df["date"])
        df["carbon_g"] = pd.to_numeric(df["carbon_g"], errors="coerce")

        user_df = df[df["user_id"] == user_id].copy()

        if user_df.empty:
              return {"message": "JSON data appended to CSV file succesfully.", "file": path, "request_id": user_id,
			"user_data": "Welcome to AI Impact Tracker!"}
        total_tokens    = int(user_df["tokens"].sum())
        total_carbon_g = float(user_df["carbon_g"].sum())
        first_date       = user_df["date"].min().date()
        days_since_start = (date.today() - first_date).days + 1
        avg_tokens_per_day = total_tokens    / days_since_start
        avg_carbon_per_day = total_carbon_g / days_since_start
        miles_driven = total_carbon_g * miles_per_kg_of_co2 /1000
        total_ml = float(user_df["water_ml"].sum())
        avg_ml_per_day = total_ml / days_since_start
        total_water_bottles = total_ml / 500
        total_kwh = float(user_df["kwh"].sum())
        avg_kwh = total_kwh / days_since_start
        return {
               "message":    "JSON data appended to CSV file successfully.",
               "file":       path,
               "request_id": user_id,
               "user_data": (
               f"Welcome to AI Impact Tracker! | "
               f"Total tokens: {total_tokens} | "
               f"Daily avg tokens: {avg_tokens_per_day:.0f} | "
               f"Total Carbon Emission: {total_carbon_g:.2f} g CO2 | "
               f"Daily avg carbon: {avg_carbon_per_day:.2f} g CO2 | "
               f"Total Miles Driven: {miles_driven:.2f} miles  | "
               f"Total Water Consumed: {total_ml:.2f} mL | "
               f"Daily avg water:  {avg_ml_per_day:.2f} mL | "
               f"Total Water Bottles: {total_water_bottles:.2f} | "
               f"Total Energy: {total_kwh:.2f} kWh | "
               f"Daily avg energy: {avg_kwh:.2f} kWh"
        ),
    }
@api.get("/plot-data2/")
async def get_plot_data(file_name: str = "impacts.csv"):
    path = os.path.join("output_data", os.path.basename(file_name))

    if not os.path.exists(path):
        return [row for row in reader]

    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [row for row in reader]

@api.get("/data2")
def get_data():
    return emission

@api.get("/calculate-awi2/{file_name}")
async def calculate_and_save_awi(file_name: str):
    try:
        #base_dir = os.path.dirname(os.path.abspath(__file__))
        # Construct paths
        input_path = os.path.join(BASE_DIR,"input_data", os.path.basename(file_name))

        # Verify input file exists
        if not os.path.exists(input_path):
            return {"error": f"Input file '{file_name}' not found on the server."}

        # Read the original data file written by POST endpoint
        emissions_df = pd.read_csv(input_path)

        if emissions_df.empty:
            return {"error": "The data file is empty."}

        # Call AWI calculation
        awis_result_dict = get_AWI(emissions_df)

        # Define the output save path on the server
        output_path = os.path.join(BASE_DIR, "output_data", "awi_results")

        # Call to csv function for awis
        awis_to_csv(awis_result_dict, output_path)

        # Return confirmation
        return {
            "status": "Success",
            "message": "AWI analysis completed and saved to the server.",
            "input_file_read": os.path.abspath(input_path),
            "output_file_saved_at": os.path.abspath(output_path)
        }
    except Exception as e:
        # Capture the entire hidden Python traceback stack map
        error_traceback = traceback.format_exc()

        # Force a return of the real error text as a clean JSON payload
        return JSONResponse(
            status_code=500,
            content={
                "error_status": "Internal Python Script Crashed",
                "error_message": str(e),
                "detailed_traceback": error_traceback
            }
        )

@api.get("/debug-paths")
async def debug_paths():
    return {
        "cwd": os.getcwd(),
        "file_location": os.path.abspath(__file__),
        "BASE_DIR": BASE_DIR,
        "data_dir_exists": os.path.exists(BASE_DIR),
        "data_dir_contents": os.listdir(BASE_DIR) if os.path.exists(BASE_DIR) else "DIRECTORY NOT FOUND"
    }

@api.post("/reload-extension-data/")
async def read_csv(req: ReadRequest, x_api_key: str = Header(default="")):
    print(f"Received key: '{x_api_key}'")
    print(f"Expected key: '{API_KEY}'")
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    user_id = req.user_id
    path = os.path.join("output_data", os.path.basename(req.file_name))

    # If the file doesn't exist yet, there is no data to read
    if not os.path.exists(path):
        return {
            "message": "No data found.",
            "request_id": user_id,
            "user_data": "Welcome to AI Impact Tracker! | Total tokens: 0 | Daily avg tokens: 0.00 | Total Carbon Emission: 0.00 g CO2 | Daily avg carbon: 0.00 g CO2 | Total Miles Driven: 0.00 miles  | Total Water Consumed: 0.00 mL | Daily avg water:  0.00 mL | Total Water Bottles: 0.00 | Total Energy: 0.00 kWh | Daily avg energy: 0.00 kWh"
        }

    # Read the existing CSV file without writing or appending anything
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df["carbon_g"] = pd.to_numeric(df["carbon_g"], errors="coerce")

    # Filter by user_id
    user_df = df[df["user_id"] == user_id].copy()

    # Handle case where user_id exists in extension but has no records in CSV yet
    if user_df.empty:
        return {
            "message": "User found but no data available.",
            "request_id": user_id,
            "user_data": "Welcome to AI Impact Tracker! | Total tokens: 0 | Daily avg tokens: 0.00 | Total Carbon Emission: 0.00 g CO2 | Daily avg carbon: 0.00 g CO2 | Total Miles Driven: 0.00 miles  | Total Water Consumed: 0.00 mL | Daily avg water:  0.00 mL | Total Water Bottles: 0.00 | Total Energy: 0.00 kWh | Daily avg energy: 0.00 kWh"
        }

    # Otherwise calculate total and average values
    total_tokens = int(user_df["tokens"].sum())
    total_carbon_g = float(user_df["carbon_g"].sum())
    first_date = user_df["date"].min().date()
    days_since_start = (date.today() - first_date).days + 1

    avg_tokens_per_day = total_tokens / days_since_start
    avg_carbon_per_day = total_carbon_g / days_since_start
    miles_driven = total_carbon_g * miles_per_kg_of_co2 / 1000
    total_ml = float(user_df["water_ml"].sum())
    avg_ml_per_day = total_ml / days_since_start
    total_water_bottles = total_ml / 500
    total_kwh = float(user_df["kwh"].sum())
    avg_kwh = total_kwh / days_since_start

    return {
        "message": "Data retrieved successfully.",
        "request_id": user_id,
        "user_data": (
            f"Welcome to AI Impact Tracker! | "
            f"Total tokens: {total_tokens} | "
            f"Daily avg tokens: {avg_tokens_per_day:.0f} | "
            f"Total Carbon Emission: {total_carbon_g:.2f} g CO2 | "
            f"Daily avg carbon: {avg_carbon_per_day:.2f} g CO2 | "
            f"Total Miles Driven: {miles_driven:.2f} miles  | "
            f"Total Water Consumed: {total_ml:.2f} mL | "
            f"Daily avg water:  {avg_ml_per_day:.2f} mL | "
            f"Total Water Bottles: {total_water_bottles:.2f} | "
            f"Total Energy: {total_kwh:.2f} kWh | "
            f"Daily avg energy: {avg_kwh:.2f} kWh"
        ),
    }

api.mount("/static-data2", StaticFiles(directory=os.path.join(BASE_DIR, "data")), name="static-data2")
