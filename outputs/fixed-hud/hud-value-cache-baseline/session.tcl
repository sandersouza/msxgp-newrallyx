if {[catch {
set save_settings_on_exit false
set renderer none
set sound_driver null
filepool add -path "/Users/sandersouza/.codex/worktrees/fixed-hud-lab/newrallyx/references/msxbios" -types system_rom -position 1
source "/Users/sandersouza/.codex/worktrees/fixed-hud-lab/newrallyx/scripts/msx/mapper_reference.tcl"
nrallyx_reference_machine "Panasonic_FS-A1WSX"
set firmwareswitch off
set throttle off
set z80_freq 3579545
set z80_freq_locked false
set limitsprites true
cart "outputs/fixed-hud/hud-value-cache-baseline/probe.rom" -romtype Normal
reset
set out "outputs/fixed-hud/hud-value-cache-baseline"
set f [open [file join $out cases.bin] rb];set data [read $f];close $f
set resets {2821 2822 2823 2824 2825 2826 2827 2828 2829 2830 2831 2832 2833 2834 2835 2836 2837 2838 2839 2840 2841 2842 2843 2844 2845 2846 2847 2848 2849 2850 2851 2852 2853 2854 2855 2856 2857 2858 2859 2860 2861 2862 2863 2864 2865 2866 2867 2868 2869 2870 2871 2872 2873 2874 2875 2876 2877 2878 2879 2880 2881 2882 2883 2884 2885 2886 2887 2888 2889 2890 2891 2892 2893 2894 2895 2896 2897 2898 2899 2900 2901 2902 2903 2904 2905 2906 2907 2908 2909 2910 2911 2912 2913 2914 2915 2916 2917 2918 2919 2920 2921 2922 2923 2924 2925 2926 2927 2928 2929 2930 2931 2932 2933 2934 2935 2936 2937 2938 2939 2940 2941 2942 2943 2944 2945 2946 2947 2948 2949 2950 2951 2952 2953 2954 2955 2956 2957 2958 2959 2960 2961 2962 2963 2964 2965 2966 2967 2968 2969 2970 2971 2972 2973 2974 2975 2976 2977 2978 2979 2980 2981 2982 2983 2984 2985 2986 2987 2988 2989 2990 2991 2992 2993 2994 2995 2996 2997 2998 2999 3000 3001 3002 3003 3004 3005 3006 3007 3008 3009 3010 3011 3012 3013 3014 3015 3016 3017 3018 3019 3020 3021 3022 3023 3024 3025 3026 3027 3028 3029 3030 3031 3032 3033 3034 3035 3036 3037 3038 3039 3040 3041 3042 3043 3044 3045 3046 3047 3048 3049 3050 3051 3052 3053 3054 3055 3056 3057 3058 3059 3060 3061 3062 3063 3064 3065 3066 3067 3068 3069 3070 3071 3072 3073 3074 3075 3076 3077 3078 3079 3080 3081 3082 3083 3084 3085 3086 3087 3088 3089 3090 3091 3092 3093 3094 3095 3096 3097 3098 3099 3100 3101 3102 3103 3104 3105 3106 3107 3108 3109 3110 3111 3112 3113 3114 3115 3116 3117 3118 3119 3120 3121 3122 3123 3124 3125 3126 3127 3128 3129 3130 3131 3132 3133 3134 3135 3136 3137 3138 3139 3140 3141 3142 3143 3144 3145 3146 3147 3148 3149 3150 3151 3152 3153 3154 3155 3156 3157 3158 3159 3160 3161 3162 3163 3164 3165 3166 3167 3168 3169 3170 3171 3172 3173 3174 3175 3176 3177 3178 3179 3180 3181 3182 3183 3184 3185 3186 3187 3188 3189 3190 3191 3192 3193 3194 3195 3196 3197 3198 3199 3200 3201 3202 3203 3204 3205 3206 3207 3208 3209 3210 3211 3212 3213 3214 3215 3216 3217 3218 3219 3220 3221 3222 3223 3224 3225 3226 3227 3228 3229 3230 3231 3232 3233 3234 3235 3236 3237 3238 3239 3240 3241 3242 3243 3244 3245 3246 3247 3248 3249 3250 3251 3252 3253 3254 3255 3256 3257 3258 3259 3260 3261 3262 3263 3264 3265 3266 3267 3268 3269 3270 3271 3272 3273 3274 3275 3276 3277 3278 3279 3280 3281 3282 3283 3284 3285 3286 3287 3288 3289 3290 3291 3292 3293 3294 3295 3296 3297 3298 3299 3300 3301 3302 3303 3304 3305 3306 3307 3308 3309 3310 3311 3312 3313 3314 3315 3316 3317 3318 3319 3320 3321 3322 3323 3324 3325 3326 3327 3328 3329 3330 3331 3332}
set result [open [file join $out actual.bin] wb];set guards [open [file join $out guards.bin] wb];set pending [open [file join $out pending.bin] wb];set native [open [file join $out native.bin] wb];set times [open [file join $out cycles.txt] w];set index 0;set started 0
proc issue {} {
 if {$::index==3333} {close $::result;close $::guards;close $::pending;close $::native;close $::times;exit 0;return}
 set at [expr {$::index*20}];binary scan [string range $::data $at [expr {$at+19}]] cu* c
 debug write memory 0xc002 [lindex $c 0]
 debug write_block memory 0xe060 [string range $::data [expr {$at+1}] [expr {$at+8}]]
 debug write_block memory 0xe0a0 [string range $::data [expr {$at+9}] [expr {$at+16}]]
 debug write memory 0xe1b0 [lindex $c 17];debug write memory 0xe00f [lindex $c 18];debug write memory 0xe26b [lindex $c 19]
 debug write_block memory 0x22b6 [string repeat z 10];debug write_block memory 0x22ce [string repeat < 50]
 set code [list 243]
 if {[lsearch -exact $::resets $::index]>=0} {lappend code 205 67 64}
 lappend code 205 114 64 205 255 67 195 64 209
 set p 0xd110;foreach v $code {debug write memory $p $v;incr p}
 set ::begin [machine_info time];reg SP 0xf380;reg PC 0xd110
}
debug set_bp 16448 {!$::started} {set ::started 1;issue}
debug set_bp 17407 {$::started} {set ::commit [machine_info time];puts -nonewline $::pending [debug read_block memory 0x2260 2];puts -nonewline $::pending [debug read_block memory 0x2000 448]}
debug set_bp 0xd140 {$::started} {
 puts $::times [list [expr {round(($::commit-$::begin)*3579545)}] [expr {round(([machine_info time]-$::commit)*3579545)}]]
 puts -nonewline $::result [debug read_block VRAM 0x1a00 56]
 puts -nonewline $::result [debug read_block VRAM 0x2c80 448]
 puts -nonewline $::guards [debug read_block memory 0x22b6 10];puts -nonewline $::guards [debug read_block memory 0x22ce 50]
 puts -nonewline $::native [debug read_block memory 0xe060 8];puts -nonewline $::native [debug read_block memory 0xe0a0 8]
 foreach addr {0xe1b0 0xe00f 0xe26b} {puts -nonewline $::native [binary format c [debug read memory $addr]]}
 incr ::index;issue
}
after time 60 {puts stderr "HUD probe timeout";exit 2}
} problem]} {puts stderr $problem;exit 2}
