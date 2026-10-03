--
-- PostgreSQL database dump
--



-- Dumped from database version 18.4
-- Dumped by pg_dump version 18.4

-- Started on 2026-09-20 15:26:11

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;



SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 226 (class 1259 OID 17478)
-- Name: buses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.buses (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    capacity integer NOT NULL,
    depot_lat double precision NOT NULL,
    depot_lng double precision NOT NULL,
    dest_lat double precision NOT NULL,
    dest_lng double precision NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    depot_address text,
    dest_address text,
    bus_type text,
    CONSTRAINT buses_capacity_check CHECK ((capacity > 0))
);


--
-- TOC entry 225 (class 1259 OID 17477)
-- Name: buses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.buses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 5957 (class 0 OID 0)
-- Dependencies: 225
-- Name: buses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.buses_id_seq OWNED BY public.buses.id;


--
-- TOC entry 228 (class 1259 OID 17494)
-- Name: passengers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.passengers (
    id integer NOT NULL,
    bus_id integer NOT NULL,
    name character varying(150),
    address text,
    lat double precision NOT NULL,
    lng double precision NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    passenger_type text
);


--
-- TOC entry 227 (class 1259 OID 17493)
-- Name: passengers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.passengers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 5958 (class 0 OID 0)
-- Dependencies: 227
-- Name: passengers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.passengers_id_seq OWNED BY public.passengers.id;


--
-- TOC entry 230 (class 1259 OID 17513)
-- Name: routes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.routes (
    id integer NOT NULL,
    bus_id integer NOT NULL,
    ordered_stops jsonb NOT NULL,
    total_distance_km numeric(10,2),
    duration_min numeric(10,1),
    used_real_roads boolean,
    geometry jsonb,
    created_at timestamp with time zone DEFAULT now(),
    legs jsonb,
    stops_detail jsonb,
    num_passengers integer
);


--
-- TOC entry 229 (class 1259 OID 17512)
-- Name: routes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.routes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 5959 (class 0 OID 0)
-- Dependencies: 229
-- Name: routes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.routes_id_seq OWNED BY public.routes.id;


--
-- TOC entry 5779 (class 2604 OID 17481)
-- Name: buses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.buses ALTER COLUMN id SET DEFAULT nextval('public.buses_id_seq'::regclass);


--
-- TOC entry 5781 (class 2604 OID 17497)
-- Name: passengers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.passengers ALTER COLUMN id SET DEFAULT nextval('public.passengers_id_seq'::regclass);


--
-- TOC entry 5783 (class 2604 OID 17516)
-- Name: routes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.routes ALTER COLUMN id SET DEFAULT nextval('public.routes_id_seq'::regclass);


--
-- TOC entry 5790 (class 2606 OID 17492)
-- Name: buses buses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.buses
    ADD CONSTRAINT buses_pkey PRIMARY KEY (id);


--
-- TOC entry 5793 (class 2606 OID 17506)
-- Name: passengers passengers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.passengers
    ADD CONSTRAINT passengers_pkey PRIMARY KEY (id);


--
-- TOC entry 5796 (class 2606 OID 17524)
-- Name: routes routes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.routes
    ADD CONSTRAINT routes_pkey PRIMARY KEY (id);


--
-- TOC entry 5791 (class 1259 OID 17530)
-- Name: idx_passengers_bus_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_passengers_bus_id ON public.passengers USING btree (bus_id);


--
-- TOC entry 5794 (class 1259 OID 17531)
-- Name: idx_routes_bus_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_routes_bus_id ON public.routes USING btree (bus_id);


--
-- TOC entry 5797 (class 2606 OID 17507)
-- Name: passengers passengers_bus_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.passengers
    ADD CONSTRAINT passengers_bus_id_fkey FOREIGN KEY (bus_id) REFERENCES public.buses(id) ON DELETE CASCADE;


--
-- TOC entry 5798 (class 2606 OID 17525)
-- Name: routes routes_bus_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.routes
    ADD CONSTRAINT routes_bus_id_fkey FOREIGN KEY (bus_id) REFERENCES public.buses(id) ON DELETE CASCADE;


-- Completed on 2026-09-20 15:26:11

--
-- PostgreSQL database dump complete
--



