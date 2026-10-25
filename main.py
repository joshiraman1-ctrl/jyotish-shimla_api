from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import swisseph as swe

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class AdvancedKundaliEngine:
    def __init__(self, ephe_path=None):
        if ephe_path:
            swe.set_ephe_path(ephe_path)

    def get_precise_julian_date(self, year, month, day, hour, minute, second, microsecond, tz_offset_hours):
        total_seconds = second + (microsecond / 1_000_000.0)
        decimal_hour = hour + (minute / 60.0) + (total_seconds / 3600.0)
        decimal_hour_ut = decimal_hour - tz_offset_hours
        jd = swe.julday(year, month, day, decimal_hour_ut)
        return jd

    def configure_settings(self, ayanamsha_mode=swe.SIDM_LAHIRI, use_topocentric=True, lat=0.0, lon=0.0, alt=0.0):
        swe.set_sid_mode(ayanamsha_mode)
        if use_topocentric:
            swe.set_topo(lon, lat, alt)

    def calculate_planets(self, jd, use_topocentric=True):
        planets = {
            "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, 
            "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER, 
            "Venus": swe.VENUS, "Saturn": swe.SATURN, "Rahu": swe.TRUE_NODE
        }
        
        calc_flag = swe.FLG_SIDEREAL | swe.FLG_SPEED
        if use_topocentric:
            calc_flag |= swe.FLG_TOPOCENTRIC

        planet_results = {}
        for name, p_id in planets.items():
            res, ret = swe.calc_ut(jd, p_id, calc_flag)
            planet_results[name] = {
                "longitude": round(res[0], 6),
                "is_retrograde": res[3] < 0
            }
            
        rahu_lon = planet_results["Rahu"]["longitude"]
        ketu_lon = (rahu_lon + 180.0) % 360.0
        planet_results["Ketu"] = {
            "longitude": round(ketu_lon, 6),
            "is_retrograde": planet_results["Rahu"]["is_retrograde"]
        }
        return planet_results

    def calculate_houses(self, jd, lat, lon, house_system=b'P'):
        cusps, ascmc = swe.houses_ex(jd, lat, lon, house_system, swe.FLG_SIDEREAL)
        return {
            "ascendant": round(ascmc[0], 6),
            "midheaven": round(ascmc[1], 6)
        }

    def calculate_vimshottari_dasha_balance(self, moon_longitude):
        nakshatra_span = 360.0 / 27.0
        nakshatra_num = int(moon_longitude // nakshatra_span)
        deg_into_nakshatra = moon_longitude % nakshatra_span
        fraction_remaining = 1.0 - (deg_into_nakshatra / nakshatra_span)
        
        dasha_lords = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
        dasha_years = [7, 20, 6, 10, 7, 18, 16, 19, 17]
        
        lord_index = nakshatra_num % 9
        ruling_lord = dasha_lords[lord_index]
        balance_years = dasha_years[lord_index] * fraction_remaining
        
        return {
            "ruling_lord": ruling_lord,
            "balance_years": round(balance_years, 2)
        }

class BirthInput(BaseModel):
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int = 0
    microsecond: int = 0
    lat: float
    lon: float
    alt: float = 0.0
    tz_offset: float = 5.5

@app.post("/api/v1/generate-kundali")
def api_generate_kundali(data: BirthInput):
    engine = AdvancedKundaliEngine()
    jd = engine.get_precise_julian_date(
        data.year, data.month, data.day, data.hour, 
        data.minute, data.second, data.microsecond, data.tz_offset
    )
    engine.configure_settings(swe.SIDEREAL_LAHIRI, use_topocentric=True, lat=data.lat, lon=data.lon, alt=data.alt)
    planets = engine.calculate_planets(jd, use_topocentric=True)
    houses = engine.calculate_houses(jd, data.lat, data.lon, b'P')
    dasha = engine.calculate_vimshottari_dasha_balance(planets["Moon"]["longitude"])
    
    return {
        "status": "success",
        "julian_date": jd,
        "ascendant": houses["ascendant"],
        "planets": planets,
        "dasha": dasha
    }
