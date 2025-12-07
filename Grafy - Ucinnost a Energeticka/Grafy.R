library(ggplot2)
library(broom)

Acadia = c("#FED789", "#023743", "#72874E", "#476F84", "#A4BED5", "#453947")

# ==========================================================================
#             e n e r g e t i c k a    k a l i b r a c e
# ==========================================================================

calib_data <- read.csv("calib_data_cebr.txt", sep = "\t")

# linear fit
fit <- lm(ENERGY ~ CHANNEL, data = calib_data)

# Extract coefficients and their uncertainties
fit_summary <- summary(fit)
coeffs <- fit_summary$coefficients

# Round 
a <- round(coeffs[1, 1], 3)  # Intercept
b <- round(coeffs[2, 1], 3)  # Slope
a_se <- round(coeffs[1, 2], 3)  # Intercept Std. Error
b_se <- round(coeffs[2, 2], 3)  # Slope Std. Error

# equation as a string
fit_equation <- paste0(
  "E = (", b, " ± ", b_se, ") × CH + (", a, " ± ", a_se, ")"
)

# plot
plot_ene <-  ggplot(data = calib_data, aes(x = CHANNEL, y = ENERGY)) +
  geom_point(color = "black", size = 5, shape=20, alpha=0.5) + 
  geom_smooth(method = "lm", se = FALSE, color = "red", linetype="dashed") +  
  labs(title = "CeBr: Energetická kalibrace", x = "Channel", y = "Energy") +
  theme_light() +
  theme(legend.position = "none") +  
  annotate("label", x = max(calib_data$CHANNEL) * 0.05, y = max(calib_data$ENERGY) * 0.9,
           label = fit_equation, hjust = 0, size = 5, color = "black", fill="white")  

plot_ene

ggsave(
  filename = "ene_cebr.png", 
  plot = plot_ene,                        
  width = 7, height = 4,  
  background = "white",
  dpi = 300                             
)

rm(a, a_se, b, b_se, coeffs, fit, fit_summary, calib_data, plot_ene, fit_equation)

# ==========================================================================
#                  k a l i b r a c n i    s p e k t r a - CEBR
# ==========================================================================


ra226 <- read.csv("Eff_CEBR/eff1.txt", sep="\t")
k40 <- read.csv("Eff_CEBR/eff2.txt", sep="\t")
th232 <- read.csv("Eff_CEBR/eff3.txt", sep="\t")
pozadi <- read.csv("Eff_CEBR/pozadi.txt", sep="\t")

# Live times
t_ra <- 234620
t_40 <- 178780
t_th <- 134650

t_bg <- 183782.67

# Ene calib coefs
ene_a0 <- 9.623
ene_a1 <- 1.379

# X: energy, Ra/K/Th/Bg - counts per second
eff_kalib = data.frame(X = ra226$X*ene_a1 + ene_a0,
                       Ra = ra226$COUNTS_k1519.2024/t_ra, 
                       K =  k40$COUNTS_k1527.2024/t_40,
                       Th = th232$COUNTS_k1535.2024/t_th,
                       Bg = pozadi$COUNTS_k1500.2024/t_bg)

# Add cols with subtracted background
eff_kalib$Ra_Bg <- eff_kalib$Ra - eff_kalib$Bg
eff_kalib$K_Bg <- eff_kalib$K - eff_kalib$Bg
eff_kalib$Th_Bg <- eff_kalib$Th - eff_kalib$Bg

# First 20 values are 0
eff_kalib_sub <- eff_kalib[21:length(eff_kalib$X), ] 

# ==============================
# SPECTRA - INCLUDING BACKGROUND
# ==============================

effplot <- ggplot(eff_kalib_sub, aes(x = X)) +
  geom_line(aes(y = Bg, color = "Pozadí"), linewidth = 1, alpha=0.8) +  
  geom_line(aes(y = Ra, color = "226-Ra"), linewidth = 1, alpha=0.8) +
  geom_line(aes(y = K, color = "40-K"), linewidth = 1, alpha=0.8) + 
  geom_line(aes(y = Th, color = "232-Th"), linewidth = 1, alpha=0.8) + 
  scale_y_log10() + 
  scale_color_manual(
    name = NULL,  # Custom legend title
    values = c("Pozadí" = Acadia[1], "226-Ra" = Acadia[2], "40-K" = Acadia[3], "232-Th" = Acadia[5])

  ) +
  labs(
    x = "Energie [kev]",
    y = "Počet impulsů (log)",
    title = "Účinnostní kalibrace, CeBr",
    subtitle = "Spektra bez odečtu pozadí"
  ) +
  geom_vline(xintercept = 1460.822, color=Acadia[3], linewidth=1.2, linetype="dotted") +
  geom_vline(xintercept = 609.312, color=Acadia[2], linewidth=1.2, linetype="dotted") +
  geom_vline(xintercept = 2614.511, color=Acadia[5], linewidth=1.2, linetype="dotted") +
  theme_bw(base_size = 14) +
  theme(
    panel.grid.major = element_line(size = 0.5),
    panel.grid.minor = element_line(size = 0.3),
    plot.title = element_text(face = "bold", size = 16),
    plot.subtitle = element_text(size = 14, face = "italic"),
    legend.position = "top" # Position the legend (optional)
  ) +
  annotate("label", x = 1461, y = max(eff_kalib_sub$Ra) * 0.85,
           label = "1460,82", hjust = 0, size = 4, color = "black", fill="white") +
  annotate("label", x = 610, y = max(eff_kalib_sub$Ra) * 0.85,
           label = "609,31", hjust = 0, size = 4, color = "black", fill="white") +
  annotate("label", x = 2615, y = max(eff_kalib_sub$Ra) * 0.85,
           label = "2614,51", hjust = 0, size = 4, color = "black", fill="white")

effplot

ggsave(
  filename = "eff_cebr.png", 
  plot = effplot,                      
  width = 7, height = 5,  
  background = "white",
  dpi = 300                             
)

# ===========================
# SPEKTRA S ODECTENYM POZADIM
# ===========================


effplot_bg <- ggplot(eff_kalib_sub, aes(x = X)) +
  geom_line(aes(y = Bg, color = "Pozadí"), linewidth = 1) +  
  geom_line(aes(y = Ra_Bg, color = "226-Ra"), linewidth = 1) +
  geom_line(aes(y = K_Bg, color = "40-K"), linewidth = 1) + 
  geom_line(aes(y = Th_Bg, color = "232-Th"), linewidth = 1) + 
  scale_y_log10() + 
  scale_color_manual(
    name = NULL,  # Custom legend title
    values = c("Pozadí" = Acadia[1], "226-Ra" = Acadia[2], "40-K" = Acadia[3], "232-Th" = Acadia[5])
    
  ) +
  labs(
    x = "Energie [kev]",
    y = "Počet impulsů (log)",
    title = "Účinnostní kalibrace, CeBr",
    subtitle = "Spektra"
  ) +
  geom_vline(xintercept = 1460.822, color=Acadia[3], linewidth=1.2, linetype="dotted") +
  geom_vline(xintercept = 609.312, color=Acadia[2], linewidth=1.2, linetype="dotted") +
  geom_vline(xintercept = 2614.511, color=Acadia[5], linewidth=1.2, linetype="dotted") +
  theme_bw(base_size = 14) +
  theme(
    panel.grid.major = element_line(size = 0.5),
    panel.grid.minor = element_line(size = 0.3),
    plot.title = element_text(face = "bold", size = 16),
    plot.subtitle = element_text(size = 14, face = "italic"),
    legend.position = "top" # Position the legend (optional)
  )

effplot_bg
