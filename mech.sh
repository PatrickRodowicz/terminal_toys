#!/bin/bash
# COMBAT MECH HUD TERMINAL v1
# Tactical mech cockpit display experience
# Run: bash mech.sh

cleanup() { tput cnorm; tput sgr0; clear; exit 0; }
trap cleanup INT TERM

# Colors — military palette
R='\e[31m'; G='\e[32m'; Y='\e[33m'; B='\e[34m'; M='\e[35m'; C='\e[36m'
BR='\e[91m'; BG='\e[92m'; BY='\e[93m'; BB='\e[94m'; BM='\e[95m'; BC='\e[96m'
W='\e[97m'; DIM='\e[2m'; BOLD='\e[1m'; RST='\e[0m'
# Primary HUD colors
HUD="${G}"       # main HUD green
HUDB="${BG}"     # bright HUD green
WARN="${BY}"     # warning amber
CRIT="${BR}"     # critical red
LABEL="${DIM}${G}" # dim label
INFO="${W}"      # info white

clear; tput civis
cols=$(tput cols)

# ── Utilities ──

hr() {
    local ch="${1:-─}" color="${2:-${DIM}${G}}"
    printf "${color}"
    for ((i = 0; i < cols; i++)); do printf "%s" "$ch"; done
    printf "${RST}\n"
}

hud_header() {
    local title="$1"
    local pad=$(( (cols - ${#title} - 8) / 2 ))
    printf "${DIM}${G}"
    for ((i = 0; i < pad; i++)); do printf "─"; done
    printf "┤${RST} ${BOLD}${HUDB}%s${RST} ${DIM}${G}├" "$title"
    for ((i = 0; i < pad; i++)); do printf "─"; done
    printf "${RST}\n"
}

type_out() {
    local text="$1" color="${2:-$HUD}" speed="${3:-0.02}"
    printf "${color}"
    for ((i = 0; i < ${#text}; i++)); do
        printf "%s" "${text:$i:1}"
        sleep "$speed"
    done
    printf "${RST}"
}

scan_line() {
    local text="$1" color="${2:-$HUD}"
    local gc='█▓▒░│┤├┼'
    printf "\r${color}"
    for ((i = 0; i < ${#text}; i++)); do
        if ((RANDOM % 5 == 0)); then
            printf "${DIM}${G}%s${RST}${color}" "${gc:$((RANDOM % ${#gc})):1}"
        else
            printf "%s" "${text:$i:1}"
        fi
    done
    sleep 0.03
    printf "\r${color}%s${RST}\n" "$text"
}

progress() {
    local label="$1" color="${2:-$HUD}" width=30 time="${3:-1.0}"
    local steps=20
    local sleep_t
    sleep_t=$(awk "BEGIN{printf \"%.3f\", $time / $steps}")
    for ((i = 0; i <= steps; i++)); do
        local filled=$((i * width / steps))
        local pct=$((i * 100 / steps))
        printf "\r${color}  %-28s ${RST}${color}[" "$label"
        for ((j = 0; j < width; j++)); do
            if ((j <= filled)); then printf "█"; else printf "${DIM}░${RST}${color}"; fi
        done
        printf "] ${INFO}%3d%%${RST}" "$pct"
        sleep "$sleep_t"
    done
    printf "\r${color}  %-28s ${RST}${color}[" "$label"
    for ((j = 0; j < width; j++)); do printf "█"; done
    printf "] ${HUDB}READY${RST}    \n"
}

spinner() {
    local msg="$1" duration="$2" color="${3:-${HUD}}"
    local frames=('/' '-' '\' '|')
    local end=$((SECONDS + duration))
    while ((SECONDS < end)); do
        for f in "${frames[@]}"; do
            printf "\r  ${HUDB}[%s]${RST} ${color}%s${RST}" "$f" "$msg"
            sleep 0.1
        done
    done
    printf "\r  ${HUDB}[✓]${RST} ${color}%s${RST}\n" "$msg"
}

warning_flash() {
    local msg="$1"
    for ((i = 0; i < 4; i++)); do
        printf "\r  ${BOLD}${CRIT}█ WARNING: %s █${RST}" "$msg"
        sleep 0.1
        printf "\r  ${DIM}${R}░ WARNING: %s ░${RST}" "$msg"
        sleep 0.1
    done
    printf "\r  ${BOLD}${CRIT}█ WARNING: %s █${RST}\n" "$msg"
}

caution_bar() {
    local msg="$1"
    printf "  ${BOLD}${WARN}╔"
    for ((i = 0; i < ${#msg} + 4; i++)); do printf "═"; done
    printf "╗${RST}\n"
    printf "  ${BOLD}${WARN}║  %s  ║${RST}\n" "$msg"
    printf "  ${BOLD}${WARN}╚"
    for ((i = 0; i < ${#msg} + 4; i++)); do printf "═"; done
    printf "╝${RST}\n"
}

randhex() { for ((i = 0; i < ${1:-8}; i++)); do printf '%x' $((RANDOM % 16)); done; }
pick() { local arr=("$@"); echo "${arr[$((RANDOM % ${#arr[@]}))]}"; }

grid_coord() {
    local letters=("ALPHA" "BRAVO" "CHARLIE" "DELTA" "ECHO" "FOXTROT" "GOLF" "HOTEL" "INDIA" "JULIET" "KILO" "LIMA")
    echo "${letters[$((RANDOM % ${#letters[@]}))]}-$((RANDOM % 9 + 1))$((RANDOM % 9 + 1))"
}

bearing() { printf "%03d" "$((RANDOM % 360))"; }
range_km() { printf "%.1f" "$(awk "BEGIN{printf \"%.1f\", ($RANDOM % 200) / 10.0 + 0.5}")"; }

bar_gauge() {
    local val="$1" max="$2" width="${3:-20}" warn_thresh="${4:-40}" crit_thresh="${5:-20}"
    local pct=$((val * 100 / max))
    local filled=$((val * width / max))
    local color="$HUDB"
    ((pct <= warn_thresh)) && color="$WARN"
    ((pct <= crit_thresh)) && color="$BOLD$CRIT"

    printf "${color}["
    for ((j = 0; j < width; j++)); do
        if ((j < filled)); then printf "█"; else printf "${DIM}░${RST}${color}"; fi
    done
    printf "]${RST} ${color}%3d%%${RST}" "$pct"
}

# Mech data
MECH_CALLSIGN=$(pick "IRONCLAD" "WARHOUND" "BASILISK" "TEMPEST" "LONGBOW" "RAVEN" "HAMMER" "VANGUARD" "SENTINEL" "REAPER")
MECH_CHASSIS=$(pick "Atlas AS7-D" "Marauder MAD-3R" "Warhammer WHM-6R" "Timber Wolf Prime" "Madcat Mk.II" "King Crab KGC-000" "Bushwacker BSW-X1" "Vulture MK-IV" "Nova Cat Prime" "Centurion CN9-A")
PILOT_CALLSIGN=$(pick "Specter" "Havoc" "Viper" "Ghost" "Jackal" "Raptor" "Nomad" "Wolf" "Fury" "Ace")

# ── Ambient chatter (tactical radio + system telemetry) ──

ambient() {
    local lines="${1:-8}" delay="${2:-1.2}"
    for ((n = 0; n < lines; n++)); do
        case $((RANDOM % 9)) in
            0) # Squad radio
                local callsigns=("Anvil-1" "Anvil-2" "Anvil-3" "Hammer-1" "Hammer-2" "Overlord" "Baseplate" "Viper-6" "Eagle-Actual" "Sabre-3")
                local msgs=("Contact, bearing $(bearing), $(range_km) klicks" \
                    "Copy, holding position at $(grid_coord)" \
                    "Moving to waypoint $(pick "Alpha" "Bravo" "Charlie" "Delta"), ETA $((RANDOM % 10 + 1)) mikes" \
                    "All clear on sector $(grid_coord)" \
                    "Roger, weapons hold" \
                    "Eyes on target, standing by" \
                    "Repositioning to high ground" \
                    "ECM coverage confirmed")
                printf "  ${DIM}${G}◄${RST} ${HUDB}%-14s${RST} ${DIM}%s${RST}\n" \
                    "$(pick "${callsigns[@]}"):" "$(pick "${msgs[@]}")" ;;
            1) # System heartbeat
                printf "  ${LABEL}[%s]${RST} ${DIM}REACTOR: %d°C | PWR: %d%% | ARMOR: %d%% | HEAT: %d%%${RST}\n" \
                    "$(date +%H:%M:%S)" "$((RANDOM % 80 + 320))" "$((RANDOM % 15 + 85))" \
                    "$((RANDOM % 20 + 75))" "$((RANDOM % 30 + 15))" ;;
            2) # Sensor ping
                local types=("MECH" "VEHICLE" "INFANTRY" "AIRCRAFT" "UNKNOWN" "VTOL" "DRONE")
                local iffs=("FRIENDLY" "HOSTILE" "UNKNOWN" "NEUTRAL")
                local iff=$(pick "${iffs[@]}")
                local iffcol="$HUDB"
                [[ "$iff" == "HOSTILE" ]] && iffcol="$CRIT"
                [[ "$iff" == "UNKNOWN" ]] && iffcol="$WARN"
                [[ "$iff" == "NEUTRAL" ]] && iffcol="$DIM"
                printf "  ${LABEL}SENSOR${RST} ${DIM}$(pick "${types[@]}") at $(bearing)° / $(range_km)km — ${RST}${iffcol}%s${RST}\n" "$iff" ;;
            3) # Terrain
                printf "  ${LABEL}NAV${RST}    ${DIM}Terrain: %s | Grade: %d%% | Footing: %s${RST}\n" \
                    "$(pick "Urban rubble" "Open field" "Forest" "Ridgeline" "River crossing" "Highway" "Industrial" "Mountain pass")" \
                    "$((RANDOM % 25))" \
                    "$(pick "SOLID" "SOFT" "UNSTABLE" "ICY" "MUD")" ;;
            4) # Weather/environment
                printf "  ${LABEL}ENV${RST}    ${DIM}Wind: %d kph %s | Vis: %s | Temp: %d°C${RST}\n" \
                    "$((RANDOM % 60 + 5))" "$(pick "N" "NE" "E" "SE" "S" "SW" "W" "NW")" \
                    "$(pick "CLEAR" "RAIN" "FOG" "DUST" "SNOW" "SMOKE")" \
                    "$((RANDOM % 50 - 10))" ;;
            5) # Ammunition tick
                printf "  ${LABEL}AMMO${RST}   ${DIM}%s: %d rds | %s: %d rds | Missiles: %d/%d${RST}\n" \
                    "$(pick "AC/20" "AC/10" "Gauss" "UAC/5" "LBX-10")" "$((RANDOM % 40 + 5))" \
                    "$(pick "MG" "Pulse" "PPC" "Flamer" "SRM")" "$((RANDOM % 200 + 20))" \
                    "$((RANDOM % 20))" "$((RANDOM % 20 + 20))" ;;
            6) # Command channel
                printf "  ${DIM}${G}◄${RST} ${BOLD}${WARN}COMMAND${RST}     ${DIM}%s${RST}\n" \
                    "$(pick "All units, maintain radio discipline" \
                           "Priority target designated at $(grid_coord)" \
                           "Air support on station, call sign Talon" \
                           "ROE updated: weapons free on confirmed hostiles" \
                           "Intel update: enemy reinforcements inbound from $(pick "north" "east" "south" "west")" \
                           "Medevac standing by at rally point $(pick "Alpha" "Bravo")" \
                           "Artillery available on request, grid $(grid_coord)")" ;;
            7) # ECM/EW
                printf "  ${LABEL}EW${RST}     ${DIM}%s${RST}\n" \
                    "$(pick "ECM field nominal — $((RANDOM % 30 + 70))% jam efficiency" \
                           "Radar warning: sweep detected, bearing $(bearing)°" \
                           "IFF transponder cycling — next ping in $((RANDOM % 10 + 2))s" \
                           "Signal intercept: encrypted burst, bearing $(bearing)°" \
                           "ECCM active — counter-jamming $((RANDOM % 3 + 1)) source(s)")" ;;
            8) # Damage control
                printf "  ${LABEL}DCTL${RST}   ${DIM}%s${RST}\n" \
                    "$(pick "Nano-repair active on left torso — $((RANDOM % 40 + 10))% complete" \
                           "Gyro compensation within tolerance" \
                           "Myomer bundle temp nominal" \
                           "Coolant circulation steady" \
                           "Ammo feed mechanism clear" \
                           "All actuators responding")" ;;
        esac
        sleep "$(awk "BEGIN{printf \"%.1f\", $delay * (0.5 + ($RANDOM % 10) / 10.0)}")"
    done
}

# ══════════════════════════════════════════
#  SCENES
# ══════════════════════════════════════════

scene_threat_board() {
    echo
    hud_header "THREAT ASSESSMENT"
    echo

    local scan_range=$(pick "2.5" "5.0" "7.5" "10.0")
    local scan_mode=$(pick "ACTIVE" "PASSIVE" "MIXED")

    printf "  ${LABEL}Sensor range: ${INFO}%s km${RST} ${LABEL}| Mode: ${INFO}%s${RST}\n\n" "$scan_range" "$scan_mode"

    # Radar sweep animation
    local sweep_chars=('─' '\\' '│' '/' '─' '\\' '│' '/')
    for ((sw = 0; sw < 16; sw++)); do
        local sc="${sweep_chars[$((sw % ${#sweep_chars[@]}))]}"
        local found=$((sw / 2))
        printf "\r  ${HUD}  SCANNING ${HUDB}%s${RST} ${DIM}contacts found: %d${RST} " "$sc" "$found"
        sleep 0.12
    done
    printf "\r  ${HUDB}  SCAN COMPLETE${RST}                                  \n\n"
    sleep 0.2

    local classifications=("MECH-ASSAULT" "MECH-HEAVY" "MECH-MEDIUM" "MECH-LIGHT" "APC" "TANK" "VTOL"
        "INFANTRY-PLT" "ARTILLERY" "DRONE-SWARM" "MECH-UNKNOWN" "VEHICLE-UNK")
    local chassis_names=("Atlas" "Hunchback" "Centurion" "Commando" "Bulldog" "Rommel" "Karnov"
        "Inf-Platoon" "Long Tom" "Wasp-Swarm" "Unidentified" "Technical")

    local num=$((RANDOM % 6 + 6))
    printf "  ${BOLD}${HUDB} ID    IFF        CLASS           BRG    RNG     SPEED    THREAT${RST}\n"
    printf "  ${DIM}${G}─────────────────────────────────────────────────────────────────────${RST}\n"

    local hostiles=0
    local friendlies=0
    local unknowns=0

    for ((i = 0; i < num; i++)); do
        local id=$(printf "T-%02d" "$((i + 1))")
        local iff=$(pick "HOSTILE" "HOSTILE" "HOSTILE" "FRIENDLY" "UNKNOWN" "NEUTRAL")
        local class_idx=$((RANDOM % ${#classifications[@]}))
        local class="${classifications[$class_idx]}"
        local brg=$(bearing)
        local rng=$(range_km)
        local spd=$((RANDOM % 120))
        local threat=$((RANDOM % 10 + 1))

        local iffcol="$HUDB"
        [[ "$iff" == "HOSTILE" ]] && iffcol="$CRIT" && hostiles=$((hostiles + 1))
        [[ "$iff" == "UNKNOWN" ]] && iffcol="$WARN" && unknowns=$((unknowns + 1))
        [[ "$iff" == "NEUTRAL" ]] && iffcol="$DIM"
        [[ "$iff" == "FRIENDLY" ]] && friendlies=$((friendlies + 1))

        local tcol="$HUDB"
        ((threat > 5)) && tcol="$WARN"
        ((threat > 8)) && tcol="$BOLD$CRIT"

        local threat_bar=""
        for ((t = 0; t < 10; t++)); do
            if ((t < threat)); then threat_bar+="█"; else threat_bar+="░"; fi
        done

        # Contact resolving animation
        printf "\r  ${DIM} %-5s classifying...${RST}          " "$id"
        sleep 0.12
        printf "\r  ${HUDB} %-5s${RST} ${iffcol}%-10s${RST} ${INFO}%-15s${RST} ${HUD}%s°${RST}  ${HUD}%5skm${RST}  ${DIM}%3d kph${RST}  ${tcol}%s${RST}          \n" \
            "$id" "$iff" "$class" "$brg" "$rng" "$spd" "$threat_bar"
        sleep 0.06
    done

    printf "  ${DIM}${G}─────────────────────────────────────────────────────────────────────${RST}\n\n"

    printf "  ${CRIT}■${RST} ${DIM}HOSTILE: %d${RST}   ${HUDB}■${RST} ${DIM}FRIENDLY: %d${RST}   ${WARN}■${RST} ${DIM}UNKNOWN: %d${RST}\n" \
        "$hostiles" "$friendlies" "$unknowns"

    if ((hostiles > 4)); then
        echo
        caution_bar "MULTIPLE HOSTILE CONTACTS — RECOMMEND TACTICAL WITHDRAWAL"
    fi
    sleep 0.5
}

scene_weapons_status() {
    echo
    hud_header "WEAPONS SYSTEMS"
    echo

    printf "  ${LABEL}Chassis: ${INFO}${MECH_CHASSIS}${RST}  ${LABEL}| Pilot: ${INFO}${PILOT_CALLSIGN}${RST}\n\n"

    spinner "Polling weapons bus" 2
    spinner "Fire control diagnostic" 1

    local targeting=$(pick "STANDARD" "ENHANCED" "ARTEMIS IV")
    printf "  ${LABEL}Fire control: ${HUDB}ONLINE${RST} ${LABEL}| Targeting: ${HUDB}${targeting}${RST}\n\n"

    local weapons=(
        "AC/20 Ultra|Right Arm|$((RANDOM % 15 + 5))|30|READY|Ballistic"
        "Gauss Rifle|Left Torso|$((RANDOM % 10 + 2))|16|READY|Ballistic"
        "ER PPC|Right Torso|∞|—|READY|Energy"
        "LRM-20|Left Torso|$((RANDOM % 60 + 20))|80|READY|Missile"
        "SRM-6|Center Torso|$((RANDOM % 20 + 4))|24|READY|Missile"
        "Medium Pulse Laser x2|Right Arm|∞|—|READY|Energy"
        "Large Laser|Left Arm|∞|—|READY|Energy"
        "Machine Gun Array|Left Arm|$((RANDOM % 800 + 200))|1000|READY|Ballistic"
        "Streak SRM-4|Right Torso|$((RANDOM % 16 + 4))|20|READY|Missile"
        "TAG Designator|Head|∞|—|READY|Support"
        "Anti-Missile System|Center Torso|$((RANDOM % 50 + 10))|60|ACTIVE|Defensive"
        "Flamer|Left Arm|$((RANDOM % 30 + 10))|40|READY|Energy"
    )

    # Pick 5-7 weapons for this loadout
    local num=$((RANDOM % 3 + 5))
    local used=()

    printf "  ${BOLD}${HUDB}  WEAPON               MOUNT        AMMO           STATUS    HEAT${RST}\n"
    printf "  ${DIM}${G}──────────────────────────────────────────────────────────────────────${RST}\n"

    local total_heat=0
    for ((w = 0; w < num; w++)); do
        local idx
        while true; do
            idx=$((RANDOM % ${#weapons[@]}))
            local dup=0
            for u in "${used[@]}"; do [[ "$u" == "$idx" ]] && dup=1 && break; done
            ((dup == 0)) && break
        done
        used+=("$idx")

        IFS='|' read -r w_name w_mount w_ammo w_max w_status w_type <<< "${weapons[$idx]}"

        # Random status override
        if ((RANDOM % 8 == 0)); then
            w_status=$(pick "DAMAGED" "JAMMED" "CYCLING")
        fi

        local scol="$HUDB"
        [[ "$w_status" == "DAMAGED" ]] && scol="$CRIT"
        [[ "$w_status" == "JAMMED" ]] && scol="$WARN"
        [[ "$w_status" == "CYCLING" ]] && scol="$WARN"

        local ammo_display=""
        if [[ "$w_ammo" == "∞" ]]; then
            ammo_display="   ∞ / ∞   "
        else
            ammo_display=$(printf "%4s / %-4s" "$w_ammo" "$w_max")
        fi

        local w_heat=$((RANDOM % 6 + 1))
        total_heat=$((total_heat + w_heat))

        # Per-weapon poll animation
        printf "\r  ${DIM}  %-20s polling...${RST}              " "$w_name"
        sleep 0.12
        printf "\r  ${INFO}  %-20s${RST} ${DIM}%-12s${RST} ${HUD}%s${RST}   ${scol}%-9s${RST} ${WARN}+%d${RST}          \n" \
            "$w_name" "$w_mount" "$ammo_display" "$w_status" "$w_heat"
        sleep 0.06
    done

    printf "  ${DIM}${G}──────────────────────────────────────────────────────────────────────${RST}\n\n"

    # Heat gauge
    local heat_current=$((RANDOM % 60 + 15))
    local heat_max=100
    printf "  ${LABEL}  HEAT LEVEL:  ${RST}"
    bar_gauge "$heat_current" "$heat_max" 30 50 25
    printf " ${DIM}${heat_current}/${heat_max}${RST}\n"

    local heat_sinks=$((RANDOM % 8 + 12))
    printf "  ${LABEL}  HEAT SINKS:  ${HUDB}%d${RST} ${DIM}($(pick "Double" "Standard") — dissipation: %d/turn)${RST}\n" \
        "$heat_sinks" "$((heat_sinks * (RANDOM % 2 + 1)))"

    if ((heat_current > 70)); then
        echo
        warning_flash "HEAT CRITICAL — REDUCE WEAPONS FIRE"
    fi

    # Targeting solution
    echo
    printf "  ${LABEL}  ACTIVE TARGET:${RST}  "
    if ((RANDOM % 3 == 0)); then
        printf "${DIM}NONE${RST}\n"
    else
        local tgt_brg=$(bearing)
        local tgt_rng=$(range_km)
        local lock_pct=$((RANDOM % 30 + 70))
        local tgt_class=$(pick "Atlas" "Hunchback" "Marauder" "Centurion" "Vulture" "Commando" "Unknown")
        printf "${CRIT}%s${RST} ${DIM}| BRG %s° | RNG %skm${RST}\n" "$tgt_class" "$tgt_brg" "$tgt_rng"
        printf "  ${LABEL}  TARGET LOCK:${RST}   "
        bar_gauge "$lock_pct" 100 20 50 25
        printf "\n"
    fi
    sleep 0.5
}

scene_damage_report() {
    echo
    hud_header "DAMAGE ASSESSMENT"
    echo

    type_out "  Running full diagnostic..." "$LABEL" 0.015; echo
    echo
    progress "Scanning armor integrity" "$HUD" 0.8
    progress "Polling internal systems" "$HUD" 0.6
    echo
    sleep 0.2

    # Mech diagram with armor values
    local head=$((RANDOM % 40 + 60))
    local ct=$((RANDOM % 50 + 40))
    local lt=$((RANDOM % 60 + 30))
    local rt=$((RANDOM % 60 + 30))
    local la=$((RANDOM % 70 + 20))
    local ra=$((RANDOM % 70 + 20))
    local ll=$((RANDOM % 50 + 40))
    local rl=$((RANDOM % 50 + 40))

    acol() {
        local v=$1
        if ((v > 70)); then printf "${HUDB}"
        elif ((v > 40)); then printf "${WARN}"
        else printf "${BOLD}${CRIT}"; fi
    }

    printf "  ${LABEL}  Chassis: ${INFO}${MECH_CHASSIS}${RST}  ${LABEL}| Total Armor: ${RST}"
    local total=$(( (head + ct + lt + rt + la + ra + ll + rl) / 8 ))
    bar_gauge "$total" 100 25 50 25
    printf "\n\n"

    # ASCII mech diagram — drawn line by line with pacing
    printf "  ${DIM}${G}             ┌─────┐${RST}\n"; sleep 0.06
    printf "  ${DIM}${G}             │${RST}$(acol $head)%3d%%${RST}${DIM}${G} │${RST}  $(acol $head)HEAD${RST}\n"; sleep 0.08
    printf "  ${DIM}${G}        ┌────┼─────┼────┐${RST}\n"; sleep 0.06
    printf "  ${DIM}${G}        │${RST}$(acol $lt)%3d%%${RST}${DIM}${G}│${RST}$(acol $ct)%3d%%${RST}${DIM}${G} │${RST}$(acol $rt)%3d%%${RST}${DIM}${G}│${RST}\n" "$lt" "$ct" "$rt"; sleep 0.08
    printf "  ${DIM}${G}   ┌────┤${RST} $(acol $lt)LT${RST} ${DIM}${G}│${RST} $(acol $ct)CT${RST}  ${DIM}${G}│${RST} $(acol $rt)RT${RST} ${DIM}${G}├────┐${RST}\n"; sleep 0.06
    printf "  ${DIM}${G}   │${RST}$(acol $la)%3d%%${RST}${DIM}${G}│    │     │    │${RST}$(acol $ra)%3d%%${RST}${DIM}${G}│${RST}\n" "$la" "$ra"; sleep 0.08
    printf "  ${DIM}${G}   │${RST} $(acol $la)LA${RST} ${DIM}${G}├────┼─────┼────┤${RST} $(acol $ra)RA${RST} ${DIM}${G}│${RST}\n"; sleep 0.06
    printf "  ${DIM}${G}   └────┘    │     │    └────┘${RST}\n"; sleep 0.06
    printf "  ${DIM}${G}          ┌──┴──┬──┴──┐${RST}\n"; sleep 0.06
    printf "  ${DIM}${G}          │${RST}$(acol $ll)%3d%%${RST}${DIM}${G} │${RST}$(acol $rl)%3d%%${RST}${DIM}${G} │${RST}\n" "$ll" "$rl"; sleep 0.08
    printf "  ${DIM}${G}          │${RST} $(acol $ll)LL${RST}  ${DIM}${G}│${RST} $(acol $rl)RL${RST}  ${DIM}${G}│${RST}\n"; sleep 0.06
    printf "  ${DIM}${G}          └─────┴─────┘${RST}\n"; sleep 0.15

    # Section summary with bar gauges
    echo
    local -a sec_names=("HEAD" "CT" "LT" "RT" "LA" "RA" "LL" "RL")
    local -a sec_vals=($head $ct $lt $rt $la $ra $ll $rl)
    for ((s = 0; s < ${#sec_names[@]}; s++)); do
        printf "  ${DIM}  %-4s${RST} " "${sec_names[$s]}"
        bar_gauge "${sec_vals[$s]}" 100 15 50 30
        printf "\n"
        sleep 0.06
    done
    echo

    # Component status — animated diagnostic sweep
    printf "  ${BOLD}${HUDB}  INTERNAL SYSTEMS DIAGNOSTIC${RST}\n"
    printf "  ${DIM}${G}──────────────────────────────────────────────────────${RST}\n"

    local components=("Fusion Reactor" "Gyroscope" "Life Support" "Sensor Suite" "Cockpit" "Myomer Bundles" "Actuators (L)" "Actuators (R)" "Jump Jets" "Comms Array")
    local num_warn=0
    local num_crit=0

    for comp in "${components[@]}"; do
        local roll=$((RANDOM % 100))
        local status="NOMINAL"
        if ((roll > 90)); then
            status=$(pick "DAMAGED" "CRITICAL")
        elif ((roll > 75)); then
            status="DEGRADED"
        fi

        local scol="$HUDB"
        local indicator="■"
        [[ "$status" == "DEGRADED" ]] && scol="$WARN" && indicator="▲" && num_warn=$((num_warn + 1))
        [[ "$status" == "DAMAGED" ]] && scol="$CRIT" && indicator="✖" && num_crit=$((num_crit + 1))
        [[ "$status" == "CRITICAL" ]] && scol="$BOLD$CRIT" && indicator="✖" && num_crit=$((num_crit + 1))

        # Scanning animation per component
        printf "\r  ${DIM}  %-18s${RST} ${DIM}scanning...${RST}" "$comp"
        sleep 0.12
        printf "\r  ${scol}  ${indicator} %-18s %s${RST}          \n" "$comp" "$status"
        sleep 0.06
    done

    printf "  ${DIM}${G}──────────────────────────────────────────────────────${RST}\n"

    if ((num_crit > 0)); then
        echo
        warning_flash "${num_crit} SYSTEM(S) CRITICAL — RIPPERDOC... ER, TECH REQUIRED"
    elif ((num_warn > 0)); then
        printf "  ${WARN}  ▲ %d system(s) degraded — monitor closely${RST}\n" "$num_warn"
    else
        printf "  ${HUDB}  ■ All systems nominal${RST}\n"
    fi
    echo

    # Repair status
    local repair_active=$((RANDOM % 3 + 1))
    printf "  ${BOLD}${HUDB}  NANO-REPAIR STATUS${RST}\n"
    printf "  ${DIM}${G}──────────────────────────────────────────────────────${RST}\n"
    for ((r = 0; r < repair_active; r++)); do
        local section=$(pick "Left Torso" "Right Arm" "Center Torso" "Left Leg" "Right Torso" "Head")
        local rpct=$((RANDOM % 80 + 10))
        local eta=$((RANDOM % 20 + 5))
        printf "    ${HUD}▸ %-16s${RST} " "$section"
        bar_gauge "$rpct" 100 20 0 0
        printf " ${DIM}ETA: ${eta}m${RST}\n"
        sleep 0.1
    done
    sleep 0.5
}

scene_sensor_sweep() {
    echo
    hud_header "DEEP SENSOR SWEEP"
    echo
    sleep 0.3

    local grid=$(grid_coord)
    local radius=$(pick "2.0" "5.0" "7.5" "10.0")
    type_out "  Initiating deep scan — grid ${grid}, radius ${radius}km" "$HUD" 0.015; echo
    echo
    sleep 0.3

    progress "Seismic analysis" "$HUD" 1.2
    progress "Thermal imaging" "$HUD" 1.0
    progress "EM spectrum scan" "$HUD" 0.8
    progress "Magnetic anomaly det." "$HUD" 1.0
    echo

    # Terrain analysis
    printf "  ${BOLD}${HUDB}  TERRAIN ANALYSIS${RST}\n"
    printf "  ${DIM}${G}──────────────────────────────────────────────────────${RST}\n"

    local terrain_features=(
        "Urban structures|4 buildings, max height 35m|Moderate cover"
        "Tree line|Dense forest, 200m depth|Heavy concealment"
        "River crossing|Width 40m, depth 2.1m|Impassable for light units"
        "Ridge line|Elevation +120m, exposed approach|Excellent firing position"
        "Bridge|Reinforced concrete, load rating 100t|Chokepoint"
        "Industrial complex|3 structures, 2 smokestacks|ECM interference"
        "Open ground|Flat terrain, minimal cover|Kill zone"
        "Highway overpass|Elevated 8m, intact|Limited concealment"
        "Crater field|Recent bombardment, soft ground|Movement penalty"
    )

    local num_terrain=$((RANDOM % 4 + 3))
    for ((t = 0; t < num_terrain; t++)); do
        local idx=$((RANDOM % ${#terrain_features[@]}))
        IFS='|' read -r t_name t_detail t_tac <<< "${terrain_features[$idx]}"
        printf "\r  ${DIM}  scanning sector %d...${RST}   " "$((t + 1))"
        sleep 0.2
        printf "\r  ${HUDB}  ▸ %-20s${RST} ${DIM}%s${RST}  ${WARN}[%s]${RST}          \n" "$t_name" "$t_detail" "$t_tac"
        sleep 0.1
    done

    echo

    # Detected signatures
    printf "  ${BOLD}${HUDB}  DETECTED SIGNATURES${RST}\n"
    printf "  ${DIM}${G}──────────────────────────────────────────────────────${RST}\n"

    local sig_types=("THERMAL" "SEISMIC" "EM" "MAGNETIC" "ACOUSTIC")
    local sig_sources=("Mech reactor signature — $(pick "heavy" "assault" "medium") class"
        "Vehicle column — estimated $((RANDOM % 6 + 2)) units"
        "Infantry position — dug in, $(pick "squad" "platoon" "company") size"
        "Power generator — $(pick "mobile command post" "field repair bay" "comm relay")"
        "Ammunition depot — high explosive signature"
        "Minefield — magnetic anomaly pattern detected"
        "Camouflaged position — thermal bloom inconsistent with terrain"
        "Artillery battery — $((RANDOM % 4 + 2)) tubes, $(pick "active" "cold")"
        "Aerospace fighter on tarmac — engines $(pick "cold" "warming up")")

    local num_sigs=$((RANDOM % 5 + 3))
    for ((s = 0; s < num_sigs; s++)); do
        local sig_type="${sig_types[$((RANDOM % ${#sig_types[@]}))]}"
        local sig_src="${sig_sources[$((RANDOM % ${#sig_sources[@]}))]}"
        local sig_brg=$(bearing)
        local sig_rng=$(range_km)
        local conf=$((RANDOM % 30 + 60))

        local ccol="$HUDB"
        ((conf < 70)) && ccol="$WARN"

        # Analyzing animation per signature
        printf "\r  ${DIM}  [%s] analyzing signal...${RST}" "$sig_type"
        sleep 0.3
        local conf_bar=""
        for ((cb = 0; cb < 10; cb++)); do
            if ((cb < conf / 10)); then conf_bar+="█"; else conf_bar+="░"; fi
        done
        printf "\r  ${DIM}  [${sig_type}]${RST} ${INFO}%s${RST}          \n" "$sig_src"
        printf "  ${DIM}         BRG %s° / RNG %skm / Confidence: ${ccol}%s %d%%${RST}\n" "$sig_brg" "$sig_rng" "$conf_bar" "$conf"
        sleep 0.15
    done
    echo

    spinner "Correlating signatures with known order of battle" 2
    printf "  ${HUDB}  Sweep complete. %d signatures catalogued.${RST}\n" "$num_sigs"
    sleep 0.5
}

scene_squad_status() {
    echo
    hud_header "LANCE TACTICAL STATUS"
    echo

    type_out "  Querying tactical network..." "$LABEL" 0.015; echo
    echo

    local callsigns=("${MECH_CALLSIGN}" "WARDEN" "STRIKER" "SCOUT" "HAMMER" "GHOST" "BULLDOG" "APEX")
    local chassis_opts=("${MECH_CHASSIS}" "Marauder MAD-3R" "Hunchback HBK-4G" "Commando COM-2D"
        "Catapult CPLT-C1" "Wolverine WVR-6R" "Shadow Hawk SHD-2H" "Thunderbolt TDR-5S"
        "Rifleman RFL-3N" "Jenner JR7-D" "Blackjack BJ-1" "Griffin GRF-1N")
    local pilot_names=("${PILOT_CALLSIGN}" "Razor" "Bishop" "Hawk" "Stone" "Frost" "Phoenix" "Cobra")
    local orders=("HOLDING" "ADVANCING" "FLANKING" "OVERWATCHING" "RETREATING" "ENGAGING" "SCOUTING" "REGROUPING")

    local lance_size=$((RANDOM % 3 + 3))

    # Link-up animation
    for ((m = 0; m < lance_size; m++)); do
        local cs="${callsigns[$((m % ${#callsigns[@]}))]}"
        printf "\r  ${HUD}  Linking: ${HUDB}%s${RST}${DIM}...${RST}  " "$cs"
        sleep 0.25
        printf "\r  ${HUDB}  ■ %s${RST} ${DIM}connected${RST}          \n" "$cs"
        sleep 0.1
    done
    echo
    sleep 0.2

    for ((m = 0; m < lance_size; m++)); do
        local cs="${callsigns[$((m % ${#callsigns[@]}))]}"
        local ch="${chassis_opts[$((m % ${#chassis_opts[@]}))]}"
        local pn="${pilot_names[$((m % ${#pilot_names[@]}))]}"
        local order="${orders[$((RANDOM % ${#orders[@]}))]}"
        local armor=$((RANDOM % 40 + 50))
        local heat=$((RANDOM % 60 + 10))
        local ammo=$((RANDOM % 50 + 30))
        local grid=$(grid_coord)

        local is_self=0
        ((m == 0)) && is_self=1

        local ocol="$HUDB"
        [[ "$order" == "RETREATING" ]] && ocol="$WARN"
        [[ "$order" == "ENGAGING" ]] && ocol="$CRIT"

        if ((is_self)); then
            printf "  ${BOLD}${HUDB}┌── %s (%s) ─── ★ YOU ─────────────────────────────┐${RST}\n" "$cs" "$pn"
        else
            printf "  ${DIM}${G}┌── ${HUDB}%s${RST} ${DIM}${G}(%s) ──────────────────────────────────────────┐${RST}\n" "$cs" "$pn"
        fi
        printf "  ${DIM}${G}│${RST}  ${DIM}Chassis:${RST} ${INFO}%-20s${RST} ${DIM}Grid:${RST} ${HUD}%-12s${RST} ${DIM}Orders:${RST} ${ocol}%s${RST}\n" "$ch" "$grid" "$order"
        printf "  ${DIM}${G}│${RST}  ${DIM}Armor${RST} "
        bar_gauge "$armor" 100 12 50 30
        printf "  ${DIM}Heat${RST} "
        bar_gauge "$heat" 100 12 60 80
        printf "  ${DIM}Ammo${RST} "
        bar_gauge "$ammo" 100 12 40 20
        printf "\n"
        if ((is_self)); then
            printf "  ${BOLD}${HUDB}└──────────────────────────────────────────────────────────┘${RST}\n"
        else
            printf "  ${DIM}${G}└──────────────────────────────────────────────────────────┘${RST}\n"
        fi
        sleep 0.3
    done

    echo
    local down=$((RANDOM % 2))
    local total=$((lance_size + down))
    printf "  ${LABEL}  Lance strength: ${HUDB}%d${RST}${LABEL}/%d mechs operational${RST}" "$lance_size" "$total"
    if ((down > 0)); then
        printf " ${CRIT}— %d destroyed${RST}" "$down"
    fi
    printf "\n"
    sleep 0.5
}

scene_engagement() {
    echo
    hud_header "!! COMBAT ENGAGEMENT !!"
    echo

    warning_flash "HOSTILE CONTACT — WEAPONS FREE"
    echo
    sleep 0.3

    local enemy_type=$(pick "Atlas AS7-D" "Marauder MAD-3R" "Hunchback HBK-4G" "King Crab KGC-000" "Warhammer WHM-6R" "Catapult CPLT-C1")
    local enemy_brg=$(bearing)
    local enemy_rng=$(range_km)
    local enemy_tons=$(pick "100" "75" "50" "100" "70" "65")

    printf "  ${CRIT}  ┌─ HOSTILE ──────────────────────────────────────┐${RST}\n"
    printf "  ${CRIT}  │${RST}  ${BOLD}${INFO}%-20s${RST} ${DIM}%st${RST}  ${DIM}BRG ${INFO}%s°${RST} ${DIM}/ RNG ${INFO}%skm${RST}  ${CRIT}│${RST}\n" \
        "$enemy_type" "$enemy_tons" "$enemy_brg" "$enemy_rng"
    printf "  ${CRIT}  └────────────────────────────────────────────────┘${RST}\n\n"
    sleep 0.3

    # Animated target lock with bar
    local lock_width=30
    local lock_steps=25
    local scare_point=$((12 + RANDOM % 6))
    for ((l = 0; l <= lock_steps; l++)); do
        local lock_pct=$((l * 100 / lock_steps))
        local filled=$((l * lock_width / lock_steps))
        local color="$WARN"
        ((lock_pct >= 80)) && color="$HUDB"

        printf "\r  ${color}  TARGET LOCK [${RST}"
        for ((j = 0; j < lock_width; j++)); do
            if ((j < filled)); then printf "${color}█${RST}"; else printf "${DIM}░${RST}"; fi
        done
        printf "${color}] %3d%%${RST}" "$lock_pct"

        # Scare event — lock drops momentarily
        if ((l == scare_point)); then
            printf "\r  ${BOLD}${CRIT}  TARGET LOCK [${RST}"
            for ((j = 0; j < lock_width; j++)); do
                if ((j < filled - 5)); then printf "${CRIT}█${RST}"; else printf "${DIM}░${RST}"; fi
            done
            printf "${CRIT}] JAMMING!${RST}  "
            sleep 0.4
            printf "\r  ${WARN}  TARGET LOCK [${RST}"
            for ((j = 0; j < lock_width; j++)); do
                if ((j < filled - 2)); then printf "${WARN}█${RST}"; else printf "${DIM}░${RST}"; fi
            done
            printf "${WARN}] RECOVERING${RST}"
            sleep 0.3
        fi

        sleep 0.06
    done
    printf "\r  ${BOLD}${HUDB}  TARGET LOCK [██████████████████████████████] LOCKED ★${RST}        \n\n"
    sleep 0.3

    # Fire sequence
    local weapons_fired=("AC/20" "Gauss Rifle" "ER PPC" "LRM-20" "SRM-6" "Large Laser" "Med Pulse Laser" "Machine Gun")
    local num_volleys=$((RANDOM % 3 + 2))
    local total_dmg_dealt=0
    local total_dmg_taken=0

    for ((v = 0; v < num_volleys; v++)); do
        hr "─" "${DIM}${WARN}"
        printf "  ${BOLD}${WARN}  ▶▶▶ VOLLEY %d ◀◀◀${RST}\n" "$((v + 1))"
        sleep 0.2

        printf "  ${HUDB}  OUTGOING:${RST}\n"
        local num_wpns=$((RANDOM % 3 + 2))
        for ((w = 0; w < num_wpns; w++)); do
            local wpn=$(pick "${weapons_fired[@]}")
            local result_roll=$((RANDOM % 10))
            local result=""
            local rcol=""

            if ((result_roll < 6)); then
                local loc=$(pick "CT" "LT" "RT" "LA" "RA" "LL" "RL" "HD")
                local dmg=$((RANDOM % 20 + 5))
                total_dmg_dealt=$((total_dmg_dealt + dmg))
                result="█ HIT — ${loc} (${dmg} DMG)"
                rcol="$HUDB"
                if [[ "$loc" == "CT" || "$loc" == "HD" ]]; then
                    result="█ HIT — ${loc} (${dmg} DMG) ★ CRITICAL STRUCTURE"
                    rcol="$BOLD$CRIT"
                fi
            elif ((result_roll < 8)); then
                result="░ MISS — target evasion"
                rcol="$DIM"
            else
                result="▒ GLANCING — deflected"
                rcol="$WARN"
            fi

            printf "  ${WARN}    ▸ %-20s${RST} ${rcol}%s${RST}\n" "$wpn" "$result"
            sleep 0.18
        done

        # Return fire — with warning
        sleep 0.3
        echo
        warning_flash "INCOMING FIRE"
        local inc_wpns=$((RANDOM % 3 + 1))
        for ((iw = 0; iw < inc_wpns; iw++)); do
            local inc_wpn=$(pick "PPC" "AC/10" "LRM-15" "SRM-4" "Large Laser" "Gauss")
            local inc_roll=$((RANDOM % 10))
            if ((inc_roll < 4)); then
                local inc_loc=$(pick "CT" "LT" "RT" "LA" "RA" "LL" "RL")
                local inc_dmg=$((RANDOM % 15 + 5))
                total_dmg_taken=$((total_dmg_taken + inc_dmg))
                printf "  ${CRIT}    ◄ %-20s${RST} ${BOLD}${CRIT}█ IMPACT — %s (-%d ARMOR)${RST}\n" "$inc_wpn" "$inc_loc" "$inc_dmg"
            else
                printf "  ${DIM}    ◄ %-20s ░ MISS${RST}\n" "$inc_wpn"
            fi
            sleep 0.12
        done
        echo
        sleep 0.3
    done

    hr "─" "${DIM}${WARN}"

    # Engagement result — dramatic
    sleep 0.3
    local result_roll=$((RANDOM % 4))
    if ((result_roll == 0)); then
        echo
        printf "  ${BOLD}${HUDB}  ╔══════════════════════════════════════╗${RST}\n"
        printf "  ${BOLD}${HUDB}  ║   ★ TARGET DESTROYED — KILL CONFIRMED  ║${RST}\n"
        printf "  ${BOLD}${HUDB}  ╚══════════════════════════════════════╝${RST}\n"
    elif ((result_roll == 1)); then
        printf "  ${WARN}  ▶ TARGET RETREATING${RST} ${DIM}— heavy damage, withdrawing bearing %s°${RST}\n" "$(bearing)"
        printf "  ${DIM}    Pursuit: $(pick "AUTHORIZED" "NEGATIVE — hold position" "at pilot discretion")${RST}\n"
    elif ((result_roll == 2)); then
        printf "  ${CRIT}  ▶ ENGAGEMENT ONGOING${RST} ${DIM}— target still combat-effective${RST}\n"
        printf "  ${DIM}    Estimated target armor: ${WARN}%d%%${RST}\n" "$((RANDOM % 40 + 15))"
    else
        printf "  ${BOLD}${HUDB}  ▶ TARGET CRIPPLED${RST} ${DIM}— mobility kill, weapons still active${RST}\n"
        printf "  ${DIM}    Recommend: $(pick "finish it" "bypass and continue mission" "capture for intel")${RST}\n"
    fi
    echo
    printf "  ${DIM}  Damage dealt: ${HUDB}%d${RST} ${DIM}| Damage taken: ${WARN}%d${RST}\n" "$total_dmg_dealt" "$total_dmg_taken"
    sleep 0.5
}

scene_comms_intercept() {
    echo
    hud_header "COMMS INTERCEPT"
    echo
    sleep 0.3

    local freq="$((RANDOM % 400 + 100)).$((RANDOM % 99))"
    local enc=$(pick "AES-MIL" "QUANTUM-7" "ROTARY-3" "NONE" "CUSTOM")
    local sig_str=$((RANDOM % 40 + 55))
    local sig_dir=$(bearing)

    # Frequency tuning animation
    printf "  ${DIM}  Scanning frequencies...${RST}\n"
    for ((ft = 0; ft < 8; ft++)); do
        local scan_f="$((RANDOM % 400 + 100)).$((RANDOM % 99))"
        printf "\r  ${DIM}  FREQ: ${HUD}%s MHz${RST} ${DIM}— ${RST}" "$scan_f"
        if ((ft < 6)); then
            printf "${DIM}static${RST}     "
        elif ((ft == 6)); then
            printf "${WARN}signal?${RST}    "
        else
            printf "${HUDB}LOCK${RST}       "
        fi
        sleep 0.2
    done
    printf "\r  ${HUDB}  FREQ: %s MHz — SIGNAL ACQUIRED${RST}                    \n\n" "$freq"
    sleep 0.2

    printf "  ${LABEL}Encryption: ${RST}"
    if [[ "$enc" == "NONE" ]]; then
        printf "${HUDB}NONE (cleartext!)${RST}\n"
    else
        printf "${WARN}%s${RST}\n" "$enc"
    fi

    # Signal strength bar
    printf "  ${LABEL}Signal:     ${RST}"
    bar_gauge "$sig_str" 100 15 40 20
    printf "  ${LABEL}| Direction: ${INFO}%s°${RST}\n\n" "$sig_dir"

    if [[ "$enc" != "NONE" ]]; then
        progress "Cracking encryption" "$HUD" 1.5
        printf "  ${HUDB}  [✓]${RST} ${DIM}Decryption key found${RST}\n"
        echo
    fi

    printf "  ${BOLD}${HUDB}  DECODED TRANSMISSION${RST}\n"
    printf "  ${DIM}${G}──────────────────────────────────────────────────────${RST}\n\n"

    local intercepts=(
        "Command, this is Bravo lance. We've lost two mechs in grid DELTA-47.\n  Requesting immediate fire support. Enemy assault lance is dug in on the ridge.\n  We cannot advance without suppression on that position."
        "All callsigns, priority message. Enemy has deployed a mobile HQ to grid\n  ECHO-31. Intel confirms the commanding officer is on-site. If we take it\n  out, their entire northern flank loses coordination. Strike window: 30 mikes."
        "Tiger Lead to Tiger 3 — fall back to rally point Bravo. Your right flank\n  is exposed. Say again, fall back NOW. Enemy scouts have your position.\n  Confirmed two light mechs circling to your six."
        "This is Firebase Romeo. We are combat ineffective. Lost the Long Toms to\n  an airstrike ten minutes ago. Counter-battery got our position. Requesting\n  emergency extraction for surviving personnel. Twelve wounded."
        "Eagle-Actual, the bridge at grid FOXTROT-19 is rigged to blow. Enemy plans\n  to funnel our armor through the canyon instead. Engineers estimate 30 minutes\n  to disarm. We need that bridge for the counterattack."
        "Supply convoy is six hours behind schedule. Enemy raiders hit the route\n  twice. Ammunition situation is critical — we're down to 40% across the\n  battalion. Recommend we consolidate and go defensive until resupply."
        "Recon confirms enemy dropship on approach vector. ETA ninety minutes.\n  Estimated payload: one full company of assault mechs. If those reinforcements\n  land, we lose the initiative. Recommend all available aerospace assets scramble."
    )

    local intercept=$(pick "${intercepts[@]}")
    while IFS= read -r line; do
        type_out "$line" "$WARN" 0.008
        echo
    done <<< "$(echo -e "$intercept")"

    echo
    printf "  ${DIM}${G}──────────────────────────────────────────────────────${RST}\n\n"

    local priority=$(pick "HIGH" "CRITICAL" "URGENT" "FLASH")
    local pcol="$WARN"
    [[ "$priority" == "CRITICAL" || "$priority" == "FLASH" ]] && pcol="$BOLD$CRIT"

    spinner "Encrypting for relay to COMMAND" 2
    spinner "Transmitting via secure channel" 1
    printf "  ${HUDB}  [✓]${RST} ${LABEL}Forwarded. Priority tag: ${pcol}%s${RST}\n" "$priority"
    sleep 0.5
}

scene_mission_brief() {
    echo
    hud_header "MISSION BRIEFING"
    echo
    sleep 0.3

    local missions=(
        "SEEK AND DESTROY|Eliminate enemy lance operating in grid $(grid_coord). Intel confirms heavy/assault class mechs guarding a supply depot. Destroy all hostiles and the depot.|Destroy enemy lance (0/4), Destroy supply depot|Enemy assault lance, possible artillery support, minefields|High"
        "RECON IN FORCE|Probe enemy defensive line along the river at $(grid_coord). Identify fortified positions, weapon emplacements, and mech deployments. Do NOT engage unless engaged.|Map 3 enemy positions, Identify command element, Exfil to rally point|Dug-in enemy forces, anti-mech turrets, surveillance drones|Moderate"
        "BASE DEFENSE|Enemy offensive expected within 2 hours at our firebase in $(grid_coord). Hold the position until reinforcements arrive. All units weapons free on confirmed hostiles.|Hold firebase for 120 minutes, Protect ammunition stores, Maintain comms uplink|Multiple enemy lances, possible aerospace strikes, infantry sappers|Extreme"
        "CONVOY ESCORT|Supply convoy en route from $(grid_coord) to $(grid_coord). Escort through contested territory. Convoy cannot stop — if it stops, it dies.|All convoy vehicles arrive intact, Maintain formation, Neutralize ambush points|Raider lances, IEDs, terrain chokepoints|High"
        "EXTRACTION|Friendly VIP stranded at crash site in $(grid_coord). Hostile forces converging. Get in, secure the VIP, get out. Expect resistance on approach and extraction.|Secure VIP alive, Extract to LZ BRAVO, Minimal collateral|Unknown enemy force strength, crash site in urban area, civilian presence|Critical"
    )

    local mission="${missions[$((RANDOM % ${#missions[@]}))]}"
    IFS='|' read -r m_type m_brief m_obj m_threat m_priority <<< "$mission"

    local pcol="$HUDB"
    [[ "$m_priority" == "High" ]] && pcol="$WARN"
    [[ "$m_priority" == "Extreme" || "$m_priority" == "Critical" ]] && pcol="$BOLD$CRIT"

    type_out "  OPERATION: ${m_type}" "$BOLD$INFO" 0.02; echo
    sleep 0.2
    printf "  ${LABEL}  Priority: ${pcol}%s${RST}  ${LABEL}| Issued: $(date +%H:%M)${RST}\n\n" "$m_priority"
    sleep 0.3

    printf "  ${LABEL}  BRIEFING:${RST}\n"
    sleep 0.2
    local words=($m_brief)
    local line="  "
    for word in "${words[@]}"; do
        if ((${#line} + ${#word} + 1 > 65)); then
            type_out "$line" "$DIM" 0.008; echo
            line="  $word"
        else
            line="$line $word"
        fi
    done
    type_out "$line" "$DIM" 0.008; echo
    echo
    sleep 0.3

    printf "  ${BOLD}${HUDB}  OBJECTIVES:${RST}\n"
    sleep 0.2
    IFS=',' read -ra objs <<< "$m_obj"
    for obj in "${objs[@]}"; do
        type_out "    □ $(echo "$obj" | sed 's/^ //')" "$HUD" 0.012; echo
        sleep 0.15
    done

    echo
    sleep 0.2
    printf "  ${BOLD}${WARN}  EXPECTED THREATS:${RST}\n"
    sleep 0.2
    IFS=',' read -ra threats <<< "$m_threat"
    for thr in "${threats[@]}"; do
        type_out "    ▸ $(echo "$thr" | sed 's/^ //')" "$CRIT" 0.012; echo
        sleep 0.15
    done

    echo
    sleep 0.2

    # Waypoints
    printf "  ${BOLD}${HUDB}  WAYPOINTS:${RST}\n"
    sleep 0.2
    local wp_names=("ALPHA" "BRAVO" "CHARLIE" "DELTA")
    local num_wp=$((RANDOM % 2 + 2))
    for ((wp = 0; wp < num_wp; wp++)); do
        type_out "    ${wp_names[$wp]}  Grid: $(grid_coord) — BRG $(bearing)° / $(range_km)km" "$HUD" 0.01; echo
        sleep 0.15
    done

    echo
    local roes=("Weapons free on confirmed hostiles. Minimize collateral."
        "Weapons hold until fired upon. Do not escalate."
        "Weapons free. No restrictions. Priority is mission success."
        "Weapons tight. Engage only designated targets.")
    type_out "  ROE: $(pick "${roes[@]}")" "$WARN" 0.012; echo
    sleep 0.5
}

scene_reactor_warning() {
    echo
    hud_header "!! REACTOR ALERT !!"
    echo

    local event=$(pick "HEAT SPIKE" "COOLANT LEAK" "POWER SURGE" "SHIELDING FAILURE" "FUEL LINE BREACH")
    warning_flash "${event} DETECTED"
    echo
    sleep 0.3

    local reactor_temp=$((RANDOM % 200 + 400))
    local safe_max=500
    local crit_max=650

    printf "  ${CRIT}  EVENT:      ${BOLD}${INFO}%s${RST}\n" "$event"
    printf "  ${CRIT}  REACTOR:    ${BOLD}${CRIT}%d°C${RST}  ${DIM}(safe: <%d°C | critical: >%d°C)${RST}\n" \
        "$reactor_temp" "$safe_max" "$crit_max"
    printf "  ${CRIT}  POWER OUT:  ${INFO}%d%%${RST}\n\n" "$((RANDOM % 40 + 50))"

    caution_bar "AUTOMATIC EMERGENCY SHUTDOWN IN $(( RANDOM % 30 + 30 ))s"
    echo

    printf "  ${BOLD}${HUDB}  EMERGENCY PROTOCOL:${RST}\n\n"

    local steps=("Reducing reactor output to 60%" "Venting excess coolant" "Activating emergency heat sinks"
        "Rerouting power from non-essential systems" "Engaging backup cooling loop"
        "Running containment diagnostic" "Stabilizing reactor core")

    for step in "${steps[@]}"; do
        spinner "$step" "$((1 + RANDOM % 2))" "$HUD"
    done

    echo

    local outcome=$((RANDOM % 3))
    if ((outcome == 0)); then
        printf "  ${BOLD}${HUDB}  REACTOR STABILIZED${RST}\n"
        printf "  ${DIM}  Temperature returning to nominal. All systems operational.${RST}\n"
    elif ((outcome == 1)); then
        printf "  ${BOLD}${WARN}  REACTOR STABLE — REDUCED CAPACITY${RST}\n"
        printf "  ${DIM}  Operating at %d%% output. Speed and weapons limited until full repair.${RST}\n" "$((RANDOM % 30 + 50))"
    else
        printf "  ${BOLD}${WARN}  REACTOR STABLE — COOLANT LOW${RST}\n"
        printf "  ${DIM}  Coolant reserves at %d%%. Sustained combat will trigger another alert.${RST}\n" "$((RANDOM % 20 + 15))"
    fi
    sleep 0.5
}

scene_resupply() {
    echo
    hud_header "FIELD RESUPPLY & REPAIR"
    echo
    sleep 0.3

    local source=$(pick "Forward Supply Point ALPHA" "Mobile Repair Bay BRAVO" "DropShip 'Resolute'" "Field Depot $(grid_coord)" "Salvage Team ECHO")
    printf "  ${LABEL}Source: ${INFO}%s${RST}\n" "$source"
    printf "  ${LABEL}Status: ${HUDB}DOCKED — RESUPPLY IN PROGRESS${RST}\n\n"
    sleep 0.3

    # Ammunition reload
    printf "  ${BOLD}${HUDB}  AMMUNITION RELOAD${RST}\n"
    printf "  ${DIM}${G}──────────────────────────────────────────────${RST}\n"

    local ammo_types=("AC/20 Ultra rounds" "Gauss slugs" "LRM-20 racks" "SRM-6 packs"
        "MG belt (1000rd)" "Streak SRM-4" "AMS charges" "Flamer fuel")
    local num_ammo=$((RANDOM % 4 + 3))
    for ((a = 0; a < num_ammo; a++)); do
        local at="${ammo_types[$((a % ${#ammo_types[@]}))]}"
        progress "$at" "$HUD" "$(awk "BEGIN{printf \"%.1f\", 0.4 + ($RANDOM % 10) / 10.0}")"
    done
    echo

    # Armor repair
    printf "  ${BOLD}${HUDB}  ARMOR PATCHING${RST}\n"
    printf "  ${DIM}${G}──────────────────────────────────────────────${RST}\n"

    local sections=("Left Torso" "Right Arm" "Center Torso" "Right Leg" "Left Arm" "Head")
    local num_repairs=$((RANDOM % 3 + 2))
    for ((r = 0; r < num_repairs; r++)); do
        local sec="${sections[$((r % ${#sections[@]}))]}"
        local plates=$((RANDOM % 5 + 1))
        progress "${sec} (${plates} plates)" "$WARN" "$(awk "BEGIN{printf \"%.1f\", 0.6 + ($RANDOM % 15) / 10.0}")"
    done
    echo

    # System recalibration
    printf "  ${BOLD}${HUDB}  SYSTEMS RECALIBRATION${RST}\n"
    printf "  ${DIM}${G}──────────────────────────────────────────────${RST}\n"

    local systems=("Targeting computer" "Gyroscope balance" "Reactor governor" "Comms array" "Sensor calibration" "Fire control linkage")
    local num_sys=$((RANDOM % 3 + 2))
    for ((s = 0; s < num_sys; s++)); do
        spinner "${systems[$((s % ${#systems[@]}))]}" "$((1 + RANDOM % 2))" "$HUD"
    done

    echo
    printf "  ${BOLD}${HUDB}  RESUPPLY COMPLETE${RST}\n"
    printf "  ${DIM}  Ammunition: ${HUDB}100%%${RST} ${DIM}| Armor: ${HUDB}%d%%${RST} ${DIM}| Systems: ${HUDB}CALIBRATED${RST}\n" "$((RANDOM % 15 + 85))"
    printf "  ${DIM}  Mech is combat-ready. Detach when clear.${RST}\n"
    sleep 0.5
}

scene_kill_tally() {
    echo
    hud_header "COMBAT LOG — THIS SORTIE"
    echo
    sleep 0.3

    local kill_count=$((RANDOM % 8 + 2))
    local assist_count=$((RANDOM % 5))
    local dmg_dealt=$((RANDOM % 400 + 100))
    local dmg_taken=$((RANDOM % 200 + 50))

    printf "  ${LABEL}Pilot: ${INFO}${PILOT_CALLSIGN}${RST}  ${LABEL}| Chassis: ${INFO}${MECH_CHASSIS}${RST}\n"
    printf "  ${LABEL}Sortie duration: ${INFO}%dh %02dm${RST}\n\n" "$((RANDOM % 4 + 1))" "$((RANDOM % 60))"

    spinner "Compiling battle recorder data" 2
    echo

    printf "  ${BOLD}${HUDB}  CONFIRMED KILLS${RST}\n"
    printf "  ${DIM}${G}──────────────────────────────────────────────────────────${RST}\n"

    local enemy_mechs=("Atlas AS7-D" "Hunchback HBK-4G" "Commando COM-2D" "Centurion CN9-A"
        "Catapult CPLT-C1" "Wolverine WVR-6R" "Jenner JR7-D" "Panther PNT-9R"
        "Stinger STG-3R" "Rifleman RFL-3N" "Shadow Hawk SHD-2H" "Griffin GRF-1N")
    local kill_methods=("AC/20 to CT" "Gauss headshot" "LRM salvo" "PPC core breach" "Ammo explosion" "Leg destruction" "CT structural failure" "Cockpit hit")

    for ((k = 0; k < kill_count; k++)); do
        local em=$(pick "${enemy_mechs[@]}")
        local km=$(pick "${kill_methods[@]}")
        local grid=$(grid_coord)
        local time="$(printf '%02d:%02d' $((RANDOM % 24)) $((RANDOM % 60)))"

        local kcol="$HUDB"
        [[ "$km" == *"headshot"* || "$km" == *"Cockpit"* ]] && kcol="$BOLD$WARN"

        # Kill entry flash
        printf "\r  ${BOLD}${CRIT}  ★ KILL CONFIRMED${RST}                              "
        sleep 0.1
        printf "\r  ${WARN}  ★${RST} ${INFO}%-22s${RST} ${kcol}%-28s${RST} ${DIM}%s %s${RST}\n" "$em" "$km" "$grid" "$time"
        sleep 0.12
    done

    printf "  ${DIM}${G}──────────────────────────────────────────────────────────${RST}\n\n"

    printf "  ${BOLD}${HUDB}  SORTIE STATISTICS${RST}\n"
    printf "  ${DIM}${G}──────────────────────────────────────────────────${RST}\n"

    local accuracy=$((RANDOM % 30 + 55))
    local shots=$((RANDOM % 200 + 50))

    # Animated stat counting
    local -a stat_labels=("Kills" "Assists" "Damage dealt" "Damage taken" "Accuracy" "Shots fired")
    local -a stat_vals=("$kill_count" "$assist_count" "${dmg_dealt} pts" "${dmg_taken} pts" "${accuracy}%" "$shots")
    local -a stat_colors=("$BOLD$HUDB" "$INFO" "$HUDB" "$WARN" "$INFO" "$INFO")

    for ((s = 0; s < ${#stat_labels[@]}; s++)); do
        printf "\r  ${DIM}  %-16s${RST} ${DIM}...${RST}" "${stat_labels[$s]}"
        sleep 0.15
        printf "\r  ${DIM}  %-16s${RST} ${stat_colors[$s]}%s${RST}        \n" "${stat_labels[$s]}" "${stat_vals[$s]}"
        sleep 0.08
    done

    printf "  ${DIM}${G}──────────────────────────────────────────────────${RST}\n"
    echo

    # Dramatic rating reveal
    local rank_titles=("Mechwarrior" "Veteran" "Elite" "Legendary" "Ace of Aces")
    local rank_idx=$((kill_count / 3))
    ((rank_idx >= ${#rank_titles[@]})) && rank_idx=$(( ${#rank_titles[@]} - 1 ))

    printf "  ${DIM}  Computing combat rating"
    for ((d = 0; d < 6; d++)); do printf "."; sleep 0.2; done
    printf "${RST}\n\n"

    local rank="${rank_titles[$rank_idx]}"
    printf "  ${BOLD}${WARN}  ╔═══════════════════════════════════╗${RST}\n"
    printf "  ${BOLD}${WARN}  ║   COMBAT RATING: %-17s║${RST}\n" "$rank"
    printf "  ${BOLD}${WARN}  ╚═══════════════════════════════════╝${RST}\n"
    sleep 0.5
}

# ══════════════════════════════════════════
#  BOOT SEQUENCE
# ══════════════════════════════════════════

printf "\n"
hr "═" "${DIM}${G}"
echo

# Reactor startup
printf "  ${DIM}${G}"
for ((i = 0; i < 3; i++)); do
    printf "."
    sleep 0.4
done
printf "${RST}\n"

scan_line "  ████████████████████████████████████████████████████████" "$DIM$G"
scan_line "  ██                                                    ██" "$DIM$G"
scan_line "  ██    ██████╗ ███╗   ██╗██╗     ██╗███╗   ██╗███████╗██" "$HUD"
scan_line "  ██   ██╔═══██╗████╗  ██║██║     ██║████╗  ██║██╔════╝██" "$HUD"
scan_line "  ██   ██║   ██║██╔██╗ ██║██║     ██║██╔██╗ ██║█████╗  ██" "$HUDB"
scan_line "  ██   ██║   ██║██║╚██╗██║██║     ██║██║╚██╗██║██╔══╝  ██" "$HUDB"
scan_line "  ██   ╚██████╔╝██║ ╚████║███████╗██║██║ ╚████║███████╗██" "$HUD"
scan_line "  ██    ╚═════╝ ╚═╝  ╚═══╝╚══════╝╚═╝╚═╝  ╚═══╝╚══════╝██" "$HUD"
scan_line "  ██                                                    ██" "$DIM$G"
scan_line "  ████████████████████████████████████████████████████████" "$DIM$G"

echo
hr "═" "${DIM}${G}"
sleep 0.2

type_out "  COMBAT MECH OPERATING SYSTEM v7.4.1 // RESTRICTED MILITARY USE" "$LABEL" 0.008; echo
type_out "  CHASSIS: ${MECH_CHASSIS}" "$HUD" 0.012; echo
type_out "  CALLSIGN: ${MECH_CALLSIGN} // PILOT: ${PILOT_CALLSIGN}" "$HUD" 0.012; echo
type_out "  $(date '+%Y-%m-%d %H:%M:%S') UTC // TACTICAL NETWORK ACTIVE" "$DIM$Y" 0.008; echo
echo

sleep 0.3
printf "${BOLD}${HUDB}  ■ REACTOR COLD START${RST}\n\n"

progress "Fusion reactor ignition" "$HUD" 1.0
progress "Coolant system pressurize" "$HUD" 0.7
progress "Myomer bundle activation" "$HUD" 0.6
progress "Gyroscope spin-up" "$HUD" 0.8
progress "Sensor array calibration" "$HUD" 0.5
progress "Weapons bus power-on" "$WARN" 0.6
progress "Comms / IFF initialization" "$HUD" 0.4
progress "Neural link synchronize" "$HUD" 0.9

echo
spinner "Connecting to tactical network" 2
spinner "Authenticating command channel" 2
spinner "Loading mission parameters" 1

echo
printf "  ${BOLD}${HUDB}■ ALL SYSTEMS NOMINAL${RST}\n"
printf "  ${HUD}  Reactor: ${HUDB}ONLINE${RST} ${HUD}| Weapons: ${HUDB}HOT${RST} ${HUD}| Sensors: ${HUDB}ACTIVE${RST}\n"
printf "  ${HUD}  Mech is combat-ready. Awaiting orders, ${PILOT_CALLSIGN}.${RST}\n"
sleep 0.8

# ══════════════════════════════════════════
#  MAIN LOOP
# ══════════════════════════════════════════

all_scenes=(scene_threat_board scene_weapons_status scene_damage_report scene_sensor_sweep
    scene_squad_status scene_engagement scene_comms_intercept scene_mission_brief
    scene_reactor_warning scene_resupply scene_kill_tally)

last_scene=-1

while true; do
    ambient $((RANDOM % 8 + 6)) 1.5

    while true; do
        pick_idx=$((RANDOM % ${#all_scenes[@]}))
        ((pick_idx != last_scene)) && break
    done
    last_scene=$pick_idx

    ${all_scenes[$pick_idx]}
done
